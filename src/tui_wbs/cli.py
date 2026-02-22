"""CLI entry point using Click."""

from __future__ import annotations

from pathlib import Path

import click


class _DefaultGroup(click.Group):
    """Insert 'run' when the first arg is not a registered subcommand."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.no_args_is_help = False  # bare `tui-wbs`도 run으로 라우팅

    def invoke(self, ctx):
        # 그룹 옵션 파싱 후 남은 args가 없으면 'run' 삽입
        if not ctx._protected_args and not ctx.args:
            ctx._protected_args = ["run"]
        return super().invoke(ctx)

    def resolve_command(self, ctx, args):
        cmd_name = args[0] if args else None
        if cmd_name and cmd_name in self.commands:
            return super().resolve_command(ctx, args)
        return super().resolve_command(ctx, ["run"] + list(args))


@click.group(cls=_DefaultGroup)
@click.option("--no-color", is_flag=True, help="Disable color output")
@click.option("--demo", is_flag=True, help="Launch with rich demo data (read-only)")
@click.version_option(package_name="tui-wbs")
@click.pass_context
def main(ctx, no_color: bool, demo: bool) -> None:
    """TUI WBS - Terminal UI Work Breakdown Structure Tool."""
    ctx.ensure_object(dict)
    ctx.obj["no_color"] = no_color
    ctx.obj["demo"] = demo


@main.command()
@click.argument("path", default=".", type=click.Path())
@click.pass_context
def run(ctx, path: str) -> None:
    """Opens a folder-based WBS project. Reads all *.wbs.md files in PATH."""
    from tui_wbs.app import WBSApp

    no_color = ctx.obj["no_color"]
    demo = ctx.obj["demo"]

    if demo:
        from tui_wbs.demo_data import get_demo_dir

        project_dir = get_demo_dir()
        app = WBSApp(project_dir=project_dir, no_color=no_color, demo_mode=True)
    else:
        project_dir = Path(path).resolve()
        if not project_dir.exists():
            if click.confirm(
                f"'{project_dir}' 폴더가 존재하지 않습니다. 새로 생성할까요?"
            ):
                project_dir.mkdir(parents=True, exist_ok=True)
                click.echo(f"폴더 생성 완료: {project_dir}")
            else:
                raise SystemExit(0)
        elif not project_dir.is_dir():
            click.echo(f"오류: '{project_dir}'는 디렉토리가 아닙니다.", err=True)
            raise SystemExit(1)
        app = WBSApp(project_dir=project_dir, no_color=no_color)
    app.run()


@main.command("init")
@click.argument("path", default=".", type=click.Path())
@click.option("--name", prompt="Project name", default="My Project", help="프로젝트 이름")
def init_cmd(path: str, name: str) -> None:
    """Initialize a new WBS project (config.toml + template .wbs.md)."""
    from tui_wbs.app import _build_sample_content
    from tui_wbs.config import save_config
    from tui_wbs.models import ProjectConfig

    project_dir = Path(path).resolve()

    # Check if .wbs.md files already exist
    existing = list(project_dir.glob("*.wbs.md"))
    if existing:
        names = ", ".join(f.name for f in existing)
        click.echo(f"WBS files already exist: {names}", err=True)
        raise SystemExit(1)

    # Create directory if needed
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create config.toml
    config = ProjectConfig(name=name)
    config.ensure_default_view()
    save_config(project_dir, config)
    click.echo(f"Created {project_dir / '.tui-wbs' / 'config.toml'}")

    # Create template .wbs.md
    wbs_path = project_dir / "project.wbs.md"
    wbs_path.write_text(_build_sample_content(name), encoding="utf-8")
    click.echo(f"Created {wbs_path}")

    click.echo(f"\nProject initialized at {project_dir}")
    click.echo("Run 'tui-wbs' to open the project.")


@main.command("init-theme")
@click.argument("path", default=".", type=click.Path())
@click.option(
    "--preset",
    default=None,
    help="Use a preset theme (e.g. catppuccin_mocha, tokyo_night, one_dark).",
)
def init_theme_cmd(path: str, preset: str | None) -> None:
    """Copy default theme to .tui-wbs/theme.yaml for customization."""
    from tui_wbs.theme import init_theme, list_presets

    project_dir = Path(path).resolve()
    if not project_dir.exists():
        if click.confirm(
            f"'{project_dir}' 폴더가 존재하지 않습니다. 새로 생성할까요?"
        ):
            project_dir.mkdir(parents=True, exist_ok=True)
            click.echo(f"폴더 생성 완료: {project_dir}")
        else:
            raise SystemExit(0)
    elif not project_dir.is_dir():
        click.echo(f"오류: '{project_dir}'는 디렉토리가 아닙니다.", err=True)
        raise SystemExit(1)
    try:
        dest = init_theme(project_dir, preset=preset)
        label = f"preset '{preset}'" if preset else "default"
        click.echo(f"Created {dest} ({label})")
    except FileExistsError as e:
        click.echo(f"Already exists: {e}", err=True)
        raise SystemExit(1)
    except FileNotFoundError as e:
        click.echo(f"오류: {e}", err=True)
        click.echo(f"사용 가능한 프리셋: {', '.join(list_presets())}")
        raise SystemExit(1)


@main.command("refresh-demo")
def refresh_demo_cmd() -> None:
    """Shift demo dates so today falls within the active phase."""
    from tui_wbs.demo_data import refresh_demo_dates

    refresh_demo_dates()
    click.echo("Demo dates refreshed to today.")
