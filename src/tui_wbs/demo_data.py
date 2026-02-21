"""Rich demo data for --demo mode.

Provides a get_demo_content() function that returns WBS markdown with:
- 5 phases, 25+ nodes, 3-level hierarchy
- 6 assignees, mixed statuses/priorities
- Relative dates anchored to today for always-current Gantt bars
- Milestones, dependencies, progress values, and memos
"""

from __future__ import annotations

from datetime import date, timedelta


def get_demo_content() -> str:
    """Return rich WBS markdown content using dates relative to today."""
    today = date.today()

    def d(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    return f"""\
# TaskFlow App v2.0
<!-- status: IN_PROGRESS | priority: HIGH | assignee: PM | start: {d(-30)} | end: {d(60)} | progress: 35 | label: planning | module: project-mgmt -->

Enterprise task management platform — full rewrite with modern stack.

## Phase 1: Discovery & Planning
<!-- status: DONE | priority: HIGH | assignee: PM | start: {d(-30)} | end: {d(-16)} | progress: 100 | label: planning | module: project-mgmt -->

### Stakeholder Interviews
<!-- status: DONE | priority: HIGH | assignee: PM | start: {d(-30)} | end: {d(-25)} | progress: 100 | label: planning | module: project-mgmt -->

Conducted 12 interviews across 4 departments.

### Competitive Analysis
<!-- status: DONE | priority: MEDIUM | assignee: Alice | start: {d(-28)} | end: {d(-22)} | progress: 100 | label: planning | module: project-mgmt -->

Reviewed 8 competing products; summarized in wiki.

### Requirements Document
<!-- status: DONE | priority: HIGH | assignee: PM | start: {d(-24)} | end: {d(-18)} | depends: Stakeholder Interviews; Competitive Analysis | progress: 100 | label: planning | module: project-mgmt -->

40-page PRD approved by steering committee.

### Planning Milestone
<!-- status: DONE | priority: HIGH | assignee: PM | start: {d(-16)} | end: {d(-16)} | milestone: true | depends: Requirements Document | label: planning | module: project-mgmt -->

## Phase 2: UX Design
<!-- status: DONE | priority: HIGH | assignee: Alice | start: {d(-18)} | end: {d(-4)} | progress: 100 | label: design | module: ux -->

### Wireframes
<!-- status: DONE | priority: HIGH | assignee: Alice | start: {d(-18)} | end: {d(-12)} | progress: 100 | label: design | module: ux -->

Low-fi wireframes for all 15 screens.

### Design System
<!-- status: DONE | priority: MEDIUM | assignee: Alice | start: {d(-14)} | end: {d(-8)} | progress: 100 | label: design | module: ux -->

Tokens, components, and Figma library published.

### Usability Testing
<!-- status: DONE | priority: HIGH | assignee: Alice | start: {d(-10)} | end: {d(-5)} | depends: Wireframes | progress: 100 | label: design | module: ux -->

5 participants, 23 findings, 8 critical fixes applied.

### Design Milestone
<!-- status: DONE | priority: HIGH | assignee: Alice | start: {d(-4)} | end: {d(-4)} | milestone: true | depends: Usability Testing; Design System | label: design | module: ux -->

## Phase 3: Core Development
<!-- status: IN_PROGRESS | priority: HIGH | assignee: Bob | start: {d(-8)} | end: {d(30)} | progress: 40 | label: backend | module: api -->

### API Gateway Setup
<!-- status: DONE | priority: HIGH | assignee: Bob | start: {d(-8)} | end: {d(-3)} | progress: 100 | label: backend | module: api -->

Express + OpenAPI spec with rate limiting.

### Authentication Service
<!-- status: DONE | priority: HIGH | assignee: Carol | start: {d(-6)} | end: {d(-1)} | depends: API Gateway Setup | progress: 100 | label: backend | module: auth -->

OAuth2 + JWT with refresh token rotation.

### Task CRUD Backend
<!-- status: IN_PROGRESS | priority: HIGH | assignee: Bob | start: {d(-2)} | end: {d(8)} | depends: Authentication Service | progress: 60 | label: backend | module: api -->

REST endpoints for task lifecycle management.

### Real-time Sync Engine
<!-- status: IN_PROGRESS | priority: MEDIUM | assignee: Carol | start: {d(0)} | end: {d(14)} | depends: Task CRUD Backend | progress: 20 | label: backend | module: realtime -->

WebSocket-based live collaboration with CRDT conflict resolution.

### Dashboard Frontend
<!-- status: IN_PROGRESS | priority: HIGH | assignee: Dave | start: {d(-1)} | end: {d(12)} | depends: API Gateway Setup | progress: 30 | label: frontend | module: ui -->

React + TanStack Query, responsive layout with dark mode.

### Notification System
<!-- status: TODO | priority: MEDIUM | assignee: Carol | start: {d(8)} | end: {d(18)} | depends: Real-time Sync Engine | label: backend | module: realtime -->

Email, push, and in-app notifications with preference center.

### Search & Filtering
<!-- status: TODO | priority: LOW | assignee: Dave | start: {d(10)} | end: {d(20)} | depends: Task CRUD Backend | label: backend | module: search -->

Full-text search with Elasticsearch, saved filter presets.

### Dev Complete Milestone
<!-- status: TODO | priority: HIGH | assignee: Bob | start: {d(30)} | end: {d(30)} | milestone: true | depends: Notification System; Search & Filtering; Dashboard Frontend | label: backend | module: api -->

## Phase 4: Quality Assurance
<!-- status: TODO | priority: HIGH | assignee: Eve | start: {d(22)} | end: {d(45)} | label: testing | module: qa -->

### Unit Test Suite
<!-- status: TODO | priority: HIGH | assignee: Eve | start: {d(22)} | end: {d(30)} | depends: Task CRUD Backend | label: testing | module: qa -->

Target 90% coverage for all backend services.

### Integration Tests
<!-- status: TODO | priority: HIGH | assignee: Eve | start: {d(28)} | end: {d(38)} | depends: Unit Test Suite | label: testing | module: qa -->

End-to-end API contract tests with Pact.

### Performance Testing
<!-- status: TODO | priority: MEDIUM | assignee: Bob | start: {d(32)} | end: {d(40)} | depends: Integration Tests | label: testing | module: qa -->

Load testing with k6; target p99 < 200ms.

### Security Audit
<!-- status: TODO | priority: HIGH | assignee: Carol | start: {d(35)} | end: {d(42)} | depends: Integration Tests | label: testing | module: qa -->

OWASP top-10 review and penetration testing.

### QA Milestone
<!-- status: TODO | priority: HIGH | assignee: Eve | start: {d(45)} | end: {d(45)} | milestone: true | depends: Performance Testing; Security Audit | label: testing | module: qa -->

## Phase 5: Launch
<!-- status: TODO | priority: HIGH | assignee: PM | start: {d(45)} | end: {d(60)} | label: ops | module: devops -->

### Staging Deployment
<!-- status: TODO | priority: HIGH | assignee: Bob | start: {d(45)} | end: {d(50)} | depends: QA Milestone | label: ops | module: devops -->

Blue-green deployment to staging environment.

### Documentation & Training
<!-- status: TODO | priority: MEDIUM | assignee: Alice | start: {d(46)} | end: {d(54)} | depends: Staging Deployment | label: docs | module: docs -->

User guide, API docs, and 3 training sessions scheduled.

### Production Rollout
<!-- status: TODO | priority: HIGH | assignee: Bob | start: {d(52)} | end: {d(58)} | depends: Documentation & Training; Staging Deployment | label: ops | module: devops -->

Canary release: 10% → 50% → 100% over 5 days.

### Launch Milestone
<!-- status: TODO | priority: HIGH | assignee: PM | start: {d(60)} | end: {d(60)} | milestone: true | depends: Production Rollout | label: ops | module: devops -->
"""
