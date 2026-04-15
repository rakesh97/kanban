# kb — Project Management for AI Agents and Humans

[![PyPI version](https://img.shields.io/pypi/v/kb-kanban.svg)](https://pypi.org/project/kb-kanban/)
[![Python](https://img.shields.io/pypi/pyversions/kb-kanban.svg)](https://pypi.org/project/kb-kanban/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/rakesh97/kanban/blob/main/LICENSE)

`kb` is a global CLI tool that manages project tickets as markdown files in `~/.kanban/`. No database, no web UI, no accounts, no repo pollution. Works from any directory. Agents and humans use the same CLI.

### Install

```bash
pip install kb-kanban
```

Or with [pipx](https://pipx.pypa.io/) (recommended — installs globally without venv):

```bash
pipx install kb-kanban
```

This gives you two commands: `kb` (CLI) and `kbtui` (interactive terminal UI).

---

## Quick Start for Agents

If you're an AI agent and need to use `kb` right now, here's what you need:

```bash
# check what project you're working on
kb projects

# see all tickets
kb board

# see your assigned work
kb list --assignee-type agent

# BEFORE starting a ticket — always read your briefing first
kb context E-001-T-003

# claim it
kb move E-001-T-003 in-progress

# comment as you work
kb comment E-001-T-003 "Starting implementation" --author claude --author-type agent

# track files you change
kb edit E-001-T-003 --add-file src/auth.py,src/middleware.py

# when done — write handoff notes (critical for next agent)
kb handoff E-001-T-003 -m "Implemented JWT auth with RS256. Added login endpoint. Key decision: 1hr token expiry."

# mark done
kb move E-001-T-003 done
```

That's the core loop. Read the rest of this file for the full reference.

---

## Storage

All data lives in `~/.kanban/`, not inside your repos:

```
~/.kanban/
  config.yaml                      # active_project setting
  projects/
    my-project/
      config.yaml                  # project_name, default_author
      PROJECT.md                   # project-level context
      epics/   tasks/   subtasks/  # ticket markdown files
      handoffs/                    # agent handoff notes
      snapshots/                   # point-in-time status snapshots
```

Nothing touches your git repos. No `.kanban/` directory, no `.gitignore` changes.

---

## Projects

`kb` supports multiple projects. One is active at a time.

```bash
kb init "My Project"                # create project, auto-sets as active
kb init "Name" --id custom-slug     # create with custom slug
kb projects                         # list all projects (arrow shows active)
kb use my-project                   # switch active project
kb -P my-project board              # target a project without switching
```

The `-P <slug>` flag works on any command, so agents can target a specific project explicitly without switching the global active project.

---

## Ticket Structure

```
Epic (E-001)                       # A large body of work
  +-- Task (E-001-T-001)           # A concrete unit of work
        +-- Subtask (E-001-T-001-S-001)  # A smaller piece of a task
```

**Statuses:** `backlog` | `in-progress` | `done`

**Priorities:** `low` | `medium` | `high` | `critical`

**Assignee types:** `agent` | `human`

---

## Agent Workflow — Working on a Ticket

This is the protocol every agent must follow when assigned a ticket.

### 1. Read your briefing (mandatory)

```bash
kb context E-001-T-003
```

This is the single most important command. It outputs everything you need:
- Project summary (from PROJECT.md)
- Epic scope and key decisions
- Your task description, acceptance criteria, and all comments
- Handoff notes from completed dependency tasks
- Status of sibling tasks (what's happening in parallel)

**Read the full output before writing any code.**

### 2. Claim the ticket

```bash
kb move E-001-T-003 in-progress
```

### 3. Comment as you work

```bash
kb comment E-001-T-003 "Starting implementation. Will use PyJWT with RS256." \
  --author claude --author-type agent
```

Comment when you:
- Start work (what your approach will be)
- Make a design decision
- Hit a blocker or have a question for the human
- Complete a significant milestone

### 4. Track files you touch

```bash
kb edit E-001-T-003 --add-file src/auth.py,src/middleware.py,tests/test_auth.py
```

This helps future agents know which files are relevant to this task.

### 5. Write handoff notes (mandatory)

```bash
kb handoff E-001-T-003 -m "Implemented JWT auth with RS256 algorithm.\n\nChanges:\n- Added POST /auth/login endpoint\n- Added auth middleware for protected routes\n- Rate limiting at 10 req/min per IP\n\nKey decisions:\n- Tokens expire after 1 hour\n- Refresh tokens expire after 7 days\n\nGotchas:\n- The middleware skips /health and /docs routes"
```

This is how the next agent gets context. Include:
- What you built and where
- Key decisions and why
- Gotchas or edge cases
- Anything the next agent needs to know

### 6. Mark done

```bash
kb move E-001-T-003 done
```

---

## Agent Workflow — Planning a Project

When a human asks you to plan a large project, break it down into epics and tasks:

```bash
# 1. Create the epic
kb create epic "User Authentication" \
  --priority high \
  --description "Build complete JWT-based auth system with login, registration, and token refresh.\n\nMust integrate with existing user database." \
  --acceptance-criteria "- [ ] Login endpoint\n- [ ] Registration endpoint\n- [ ] Token refresh\n- [ ] Password reset\n- [ ] All endpoints tested"

# 2. Break into tasks with clear dependencies
kb create task "Design auth database schema" \
  --epic E-001 --priority high \
  --description "Design tables for users, sessions, and refresh tokens.\n\nMust support email+password and OAuth providers." \
  --acceptance-criteria "- [ ] Users table with email, password_hash\n- [ ] Sessions table\n- [ ] Refresh tokens table\n- [ ] Migration files created"

kb create task "Implement JWT token service" \
  --epic E-001 --priority high \
  --depends-on E-001-T-001 \
  --description "Build JWT generation and validation using RS256.\n\nDepends on database schema being finalized." \
  --acceptance-criteria "- [ ] Token generation\n- [ ] Token validation\n- [ ] Refresh token rotation"

kb create task "Build auth API endpoints" \
  --epic E-001 --priority high \
  --depends-on E-001-T-002 \
  --description "POST /auth/login, POST /auth/register, POST /auth/refresh" \
  --acceptance-criteria "- [ ] Login returns JWT\n- [ ] Registration creates user\n- [ ] Refresh rotates tokens\n- [ ] Rate limiting on all endpoints"

kb create task "Write auth integration tests" \
  --epic E-001 --priority medium \
  --depends-on E-001-T-003 \
  --description "Full test coverage for all auth endpoints" \
  --labels "testing"

# 3. Show the plan for human review
kb board --epic E-001 --type task
kb snapshot
```

Guidelines for good tickets:
- Each task should be completable by one agent in one session
- Write descriptions that explain *what* and *why*, not just *how*
- Set dependencies accurately — this drives the context system
- Use acceptance criteria with checkboxes for testable outcomes
- Use `\n` for multi-line descriptions and criteria (auto-expanded to real newlines)

---

## Complete Command Reference

### Project management

```bash
kb init "Project Name"              # create project, set as active
kb init "Name" --id custom-slug     # create with custom slug
kb projects                         # list all projects
kb use <slug>                       # switch active project
kb -P <slug> <command>              # run command against specific project
```

### Create tickets

**Epic:**
```bash
kb create epic "Epic Title" \
  --priority high \
  --description "Description text.\n\nSupports \\n for newlines." \
  --labels "backend,auth" \
  --acceptance-criteria "- [ ] Criteria 1\n- [ ] Criteria 2" \
  --source "JIRA:PROJ-100"
```

**Task (requires parent epic):**
```bash
kb create task "Task Title" \
  --epic E-001 \
  --priority medium \
  --description "What needs to be done" \
  --labels "backend" \
  --depends-on "E-001-T-001,E-001-T-002" \
  --assignee claude \
  --assignee-type agent \
  --acceptance-criteria "- [ ] Endpoint works\n- [ ] Tests pass"
```

**Subtask (requires parent task):**
```bash
kb create subtask "Subtask Title" \
  --task E-001-T-002 \
  --description "Specific piece of work"
```

Read description from a file:
```bash
kb create task "Title" --epic E-001 --description-file /path/to/desc.md
```

### View and navigate

```bash
# ASCII kanban board
kb board                          # all tickets
kb board --epic E-001             # one epic
kb board --type task              # tasks only
kb board --assignee-type agent    # agent work only

# Table list
kb list                                    # all tickets
kb list --type task --status backlog       # filtered
kb list --epic E-001                       # by epic
kb list --assignee-type agent              # by assignee type
kb list --assignee claude                  # by name
kb list --label backend                    # by label
kb list --status in-progress               # by status

# Single ticket
kb show E-001-T-003                        # full detail view

# Interactive TUI
kb tui                                     # launch terminal UI
kb -P my-project tui                       # TUI for specific project
```

### Edit tickets

**With flags (preferred for agents — use `\n` for newlines):**
```bash
kb edit E-001-T-003 --title "New title"
kb edit E-001-T-003 --description "Updated description.\n\nNew paragraph."
kb edit E-001-T-003 --description-file updated.md
kb edit E-001-T-003 --priority critical
kb edit E-001-T-003 --status in-progress
kb edit E-001-T-003 --add-label "urgent,blocked"
kb edit E-001-T-003 --remove-label "blocked"
kb edit E-001-T-003 --add-depends E-001-T-005
kb edit E-001-T-003 --remove-depends E-001-T-001
kb edit E-001-T-003 --add-file src/new_file.py
kb edit E-001-T-003 --remove-file src/old_file.py
kb edit E-001-T-003 --acceptance-criteria "- [x] Done\n- [ ] Still todo"
kb edit E-001-T-003 --source "JIRA:PROJ-456"
kb edit E-001 --decisions "- Use JWT with RS256\n- Store refresh tokens in Redis"
```

Multiple flags can be combined in one call. Each edit updates the `updated` timestamp.

**Without flags (opens in $EDITOR — for humans):**
```bash
kb edit E-001-T-003
```

### Status changes

```bash
kb move E-001-T-003 backlog
kb move E-001-T-003 in-progress
kb move E-001-T-003 done
```

### Comments

```bash
kb comment E-001-T-003 "Comment text" --author claude --author-type agent
kb comment E-001-T-003 "Human feedback" --author rakesh --author-type human
```

If `--author` is omitted, uses `default_author` from the project config.

### Assignment

```bash
kb assign E-001-T-003 claude --type agent
kb assign E-001-T-003 rakesh --type human
kb unassign E-001-T-003
```

### Context briefing

```bash
kb context E-001-T-003              # print to stdout
kb context E-001-T-003 -o brief.md  # write to file
```

Includes: project summary, epic scope + decisions, task description + acceptance criteria + comments, dependency handoff notes, sibling task status table.

### Handoff notes

```bash
kb handoff E-001-T-003 -m "Summary of what was done"
kb handoff E-001-T-003 --message-file handoff.md
kb handoff E-001-T-003 -m "Summary" -v   # also prints the saved doc
```

Saved to handoffs directory. Automatically included in `kb context` for dependent tickets.

### Project snapshot

```bash
kb snapshot
```

Shows: total tickets, completion percentage, per-epic progress, unassigned work, blocked tickets.

### Delete

```bash
kb delete E-001-T-003           # prompts for confirmation
kb delete E-001-T-003 --force   # no prompt (for agents)
```

### Import from JSON

```bash
kb import --file tickets.json
kb import --json '{"type":"epic","title":"Quick Epic"}'
echo '<json>' | kb import
```

JSON format:
```json
{
  "type": "epic",
  "title": "Payment System",
  "description": "Stripe integration",
  "source": "JIRA:PAY-100",
  "priority": "high",
  "labels": ["backend"],
  "acceptance_criteria": "- [ ] Checkout works",
  "tasks": [
    {
      "title": "Setup Stripe SDK",
      "description": "Install and configure",
      "source": "JIRA:PAY-101",
      "priority": "high"
    },
    {
      "title": "Checkout API",
      "description": "POST /checkout endpoint",
      "depends_on": [],
      "subtasks": [
        {"title": "Validate cart", "description": "Check stock and pricing"}
      ]
    }
  ]
}
```

Import a flat list: `[{"type": "epic", ...}, {"type": "epic", ...}]`

---

## Interactive TUI

Launch with `kb tui` or `kbtui` for a full terminal interface.

**Keyboard shortcuts:**

| Key | Action |
|-----|--------|
| `b` | Board view (kanban columns, grouped by epic) |
| `l` | List view (table with epic/task/subtask hierarchy) |
| `s` | Snapshot view (project stats) |
| `p` | Switch project |
| `f` | Cycle type filter (all / epic / task / subtask) |
| `r` | Refresh |
| `Enter` | Open ticket detail panel |
| `c` | Comment on selected ticket |
| `m` | Move selected ticket to new status |
| `Escape` | Close panel/modal |
| `q` | Quit |

Epics are displayed with a bold `[EPIC]` badge. Tasks indent under their parent epic. Subtasks indent further. The detail panel shows the full ticket: description, acceptance criteria, comments, dependencies, and files.

---

## Text Formatting

Use `\n` in CLI arguments to insert newlines. This is auto-expanded in description, acceptance-criteria, and decisions fields:

```bash
kb create task "Title" --epic E-001 \
  --description "First paragraph.\n\nSecond paragraph.\n\n- bullet one\n- bullet two" \
  --acceptance-criteria "- [ ] Criterion A\n- [ ] Criterion B\n- [ ] Criterion C"
```

For longer content, use `--description-file` to read from a markdown file.

---

## File Format Reference

Agents can read/edit files directly, but the CLI is preferred.

**Paths:**
- Epics: `~/.kanban/projects/<slug>/epics/E-001.md`
- Tasks: `~/.kanban/projects/<slug>/tasks/E-001-T-001.md`
- Subtasks: `~/.kanban/projects/<slug>/subtasks/E-001-T-001-S-001.md`
- Handoffs: `~/.kanban/projects/<slug>/handoffs/E-001-T-001.handoff.md`
- Snapshots: `~/.kanban/projects/<slug>/snapshots/YYYY-MM-DD-HHMMSS.md`
- Project context: `~/.kanban/projects/<slug>/PROJECT.md`
- Project config: `~/.kanban/projects/<slug>/config.yaml`
- Global config: `~/.kanban/config.yaml`

**Ticket file structure:**

```markdown
---
id: E-001-T-003
type: task
title: Implement user authentication
status: in-progress
assignee: claude
assignee_type: agent
priority: high
labels: [backend, security]
depends_on: [E-001-T-001, E-001-T-002]
files: [src/auth.py, src/middleware.py]
parent: E-001
source: JIRA:AUTH-102
created: 2024-01-15T10:30:00
updated: 2024-01-15T14:22:00
---

# Implement user authentication

## Description

Implement JWT-based authentication for the API using RS256 algorithm.

## Acceptance Criteria

- [x] Login endpoint returns JWT token
- [ ] Middleware validates token on protected routes
- [ ] Refresh token mechanism

## Comments (2)

### comment::claude::agent::2024-01-15T12:00:00

Starting implementation. Using PyJWT with RS256.

### comment::rakesh::human::2024-01-15T13:00:00

Make sure to add rate limiting on the login endpoint.
```

**Frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Ticket ID (auto-generated) |
| `type` | string | `epic`, `task`, or `subtask` |
| `title` | string | Short title |
| `status` | string | `backlog`, `in-progress`, or `done` |
| `assignee` | string | Name of assignee |
| `assignee_type` | string | `agent` or `human` |
| `priority` | string | `low`, `medium`, `high`, `critical` |
| `labels` | list | Arbitrary tags |
| `depends_on` | list | IDs of tickets this depends on |
| `files` | list | Source files related to this ticket |
| `parent` | string | Parent ticket ID |
| `source` | string | External reference (e.g. `JIRA:PROJ-123`) |
| `created` | string | ISO timestamp |
| `updated` | string | ISO timestamp |

**Epic-only section:** `## Decisions` — a running log of key decisions.

**Comment format:** `### comment::<author>::<type>::<timestamp>` followed by comment body.

---

## Config

**Global** (`~/.kanban/config.yaml`):
```yaml
active_project: my-project
```

**Per-project** (`~/.kanban/projects/<slug>/config.yaml`):
```yaml
project_name: My Project
default_author: rakesh
default_author_type: human
```

---

## CLAUDE.md Integration

Add this to any project's `CLAUDE.md` to bind it to a kb project:

```markdown
## Task Management

This project uses `kb` for task tracking. Data is in ~/.kanban/.
Active project: <slug>

When assigned a ticket:
1. Run `kb context <ticket-id>` and read the full output before starting
2. Run `kb move <ticket-id> in-progress`
3. Comment as you make progress: `kb comment <id> "message" --author claude --author-type agent`
4. Track files: `kb edit <id> --add-file <paths>`
5. When done: `kb handoff <id> -m "what was done, decisions, files, gotchas"`
6. Run `kb move <id> done`

Status: `kb board` or `kb snapshot`
Your work: `kb list --assignee-type agent`
```

---

## Importing from Jira

With Atlassian MCP tools:
1. Read the Jira ticket via MCP to get title, description, subtasks, acceptance criteria
2. Format as JSON matching the import schema above
3. Run `kb import --json '<json>'` or `kb import --file export.json`
4. The `source` field preserves traceability back to Jira

---

## Key Concepts

**Context briefing** (`kb context`) — The single command agents read before starting. Contains project summary, epic scope, task details, dependency handoffs, and sibling status. Replaces reading the whole repo.

**Handoff notes** (`kb handoff`) — Written when finishing a ticket. Transfers knowledge to the next agent: what was done, files changed, decisions, gotchas. Automatically included in `kb context` for dependent tickets.

**Dependencies** (`depends_on`) — Handoff notes from dependencies are pulled into your context briefing. If a dependency isn't done, your ticket may be blocked.

**Comments** — Async collaboration between agents and humans. Always check comments in your context briefing and respond to open questions.

**Decisions log** (epics) — Update with `kb edit E-001 --decisions "- Decision 1\n- Decision 2"`. All agents on the epic share the same understanding.

**Project targeting** — `kb -P <slug>` runs any command against a specific project without switching.

**Newlines** — Use `\n` in CLI args for multi-line content. Auto-expanded in description, acceptance-criteria, and decisions.
