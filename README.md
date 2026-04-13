# kb — Project Management for AI Agents and Humans

`kb` is a global CLI tool that manages project tickets as markdown files in `~/.kanban/`. No database, no web UI, no accounts, no repo pollution. Works from any directory. Agents and humans use the same CLI.

## Why This Exists

When AI agents work on large projects, they need:
- Structured task breakdowns (not just a chat prompt)
- Context about what was decided, what's done, and what's blocked
- A way to hand off knowledge between agents without re-reading the entire repo
- Collaboration with humans through comments and reviews

`kb` provides all of this through a global CLI that any agent can call from anywhere.

---

## Install

`kb` is already installed globally. Run `kb --version` to verify. If not available:

```bash
pipx install -e /path/to/kanban
```

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
    another-project/
      ...
```

Nothing touches your git repos. No `.kanban/` directory, no `.gitignore` changes, no coworker questions.

---

## Projects

`kb` supports multiple projects. One is active at a time.

```bash
# create a project (auto-sets it as active)
kb init "My Project"

# create another
kb init "Work Auth System"

# list all projects (arrow shows active)
kb projects

# switch active project
kb use my-project

# run any command against a specific project without switching
kb -P work-auth-system board
```

The `-P <slug>` flag works on any command, so agents can target a specific project explicitly.

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

## Agent Workflow

This is the standard protocol. Follow these steps when working on a ticket.

### Step 1: Read your briefing

```bash
kb context E-001-T-003
```

This outputs a single document containing:
- Project summary (from PROJECT.md)
- Epic scope and key decisions
- Your task description, acceptance criteria, and all comments
- Handoff notes from completed dependency tasks
- Status of sibling tasks (what's happening in parallel)

Read this output completely before starting work.

### Step 2: Claim the ticket

```bash
kb move E-001-T-003 in-progress
```

### Step 3: Comment as you work

```bash
kb comment E-001-T-003 "Starting implementation. Will use PyJWT with RS256." \
  --author claude --author-type agent
```

Comment when you:
- Start work (what your approach will be)
- Hit a blocker or make a design decision
- Have a question for the human
- Complete a significant milestone

### Step 4: Track files you touch

```bash
kb edit E-001-T-003 --add-file src/auth.py,src/middleware.py,tests/test_auth.py
```

This helps future agents know which files are relevant.

### Step 5: Write handoff notes when done

```bash
kb handoff E-001-T-003 -m "Implemented JWT auth with RS256 algorithm. \
Added login endpoint at POST /auth/login. Added auth middleware that \
validates Bearer tokens. Rate limiting added at 10 req/min per IP. \
Key decision: tokens expire after 1 hour, refresh tokens after 7 days."
```

Write handoff notes that tell the next agent:
- What you built and where
- Key decisions you made and why
- Anything the next agent needs to know
- Gotchas or edge cases

### Step 6: Mark done

```bash
kb move E-001-T-003 done
```

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
  --description "What this epic is about" \
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

You can also read description from a file:
```bash
kb create task "Title" --epic E-001 --description-file /path/to/desc.md
```

### View the board

```bash
kb board                          # all tickets
kb board --epic E-001             # tickets in one epic
kb board --type task              # tasks only
kb board --assignee-type agent    # agent-assigned only
```

### List tickets

```bash
kb list                                    # all tickets
kb list --type task --status backlog       # backlog tasks
kb list --epic E-001                       # everything in an epic
kb list --assignee-type agent              # agent work
kb list --assignee claude                  # specific assignee
kb list --label backend                    # by label
kb list --status in-progress               # what's active
```

### Show ticket details

```bash
kb show E-001-T-003
```

Displays: metadata, description, acceptance criteria, decisions (epics), and all comments.

### Edit tickets

**With flags (preferred for agents):**
```bash
kb edit E-001-T-003 --title "New title"
kb edit E-001-T-003 --description "Updated description"
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

### Move ticket status

```bash
kb move E-001-T-003 backlog
kb move E-001-T-003 in-progress
kb move E-001-T-003 done
```

### Add comments

```bash
kb comment E-001-T-003 "Comment text here" --author claude --author-type agent
kb comment E-001-T-003 "Human feedback" --author rakesh --author-type human
```

If `--author` is omitted, uses `default_author` from the project's config.yaml.

### Assign / unassign

```bash
kb assign E-001-T-003 claude --type agent
kb assign E-001-T-003 rakesh --type human
kb unassign E-001-T-003
```

### Generate context briefing

```bash
kb context E-001-T-003              # print to stdout
kb context E-001-T-003 -o brief.md  # write to file
```

The context document includes:
1. Project summary (from PROJECT.md)
2. Epic description and decisions
3. Task description, acceptance criteria, comments
4. Handoff notes from dependency tasks
5. Sibling task status table

### Write handoff notes

```bash
kb handoff E-001-T-003 -m "Summary of what was done"
kb handoff E-001-T-003 --message-file handoff.md
kb handoff E-001-T-003 -m "Summary" -v   # also prints the handoff
```

Handoffs are saved and automatically included when future agents run `kb context` on dependent tickets.

### Project snapshot

```bash
kb snapshot
```

Outputs:
- Total ticket count and completion percentage
- Per-epic progress breakdown
- Unassigned work
- Blocked tickets (dependencies not met)

### Delete a ticket

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

**JSON format for a full epic with tasks and subtasks:**

```json
{
  "type": "epic",
  "title": "Payment System",
  "description": "Stripe integration for checkout",
  "source": "JIRA:PAY-100",
  "priority": "high",
  "labels": ["backend", "payments"],
  "acceptance_criteria": "- [ ] Checkout works\n- [ ] Refunds work",
  "tasks": [
    {
      "title": "Setup Stripe SDK",
      "description": "Install and configure stripe-python",
      "source": "JIRA:PAY-101",
      "priority": "high",
      "labels": ["backend"]
    },
    {
      "title": "Checkout API",
      "description": "POST /checkout endpoint",
      "source": "JIRA:PAY-102",
      "depends_on": [],
      "subtasks": [
        {
          "title": "Validate cart contents",
          "description": "Check stock and pricing before charging"
        }
      ]
    }
  ]
}
```

You can also import a flat list:
```json
[
  {"type": "epic", "title": "Epic 1", "tasks": [...]},
  {"type": "epic", "title": "Epic 2", "tasks": [...]}
]
```

---

## Planning Workflow (For Agents Creating Tickets)

When asked to plan a large project, follow this pattern:

```bash
# 1. Create the epic
kb create epic "Feature Name" --priority high \
  --description "Full description of the feature scope" \
  --acceptance-criteria "High-level criteria for the whole epic"

# 2. Break it into tasks
kb create task "First task" --epic E-001 --priority high \
  --description "Detailed description" \
  --acceptance-criteria "- [ ] Specific criteria"

kb create task "Second task" --epic E-001 --priority high \
  --depends-on E-001-T-001 \
  --description "This task depends on the first"

kb create task "Third task" --epic E-001 \
  --depends-on E-001-T-001,E-001-T-002 \
  --description "Depends on both previous tasks"

# 3. Add subtasks where needed
kb create subtask "Specific subtask" --task E-001-T-002 \
  --description "A granular piece of work"

# 4. Show the plan for human review
kb board --epic E-001 --type task
kb snapshot
```

Guidelines for creating good tickets:
- Each task should be completable by one agent in one session
- Write clear descriptions that explain *what* and *why*, not just *how*
- Set dependencies accurately — this drives the context system
- Use acceptance criteria with checkboxes for testable outcomes
- Label tasks that need human review or decisions

---

## File Format Reference

Agents can read and edit ticket files directly if needed, but the CLI is preferred.

**Location mapping:**
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
| `parent` | string | Parent ticket ID (epic for tasks, task for subtasks) |
| `source` | string | External reference (e.g. `JIRA:PROJ-123`) |
| `created` | string | ISO timestamp |
| `updated` | string | ISO timestamp |

**Epic-only section:** `## Decisions` — a running log of key decisions made during the epic.

**Comment format:** `### comment::<author>::<type>::<timestamp>` followed by the comment body.

---

## Config

**Global config** (`~/.kanban/config.yaml`):
```yaml
active_project: my-project
```

**Project config** (`~/.kanban/projects/<slug>/config.yaml`):
```yaml
project_name: My Project
default_author: rakesh
default_author_type: human
```

`default_author` and `default_author_type` are used when `--author` is omitted from `kb comment`.

---

## CLAUDE.md Integration

Add this to any project's `CLAUDE.md` so agents automatically follow the protocol:

```markdown
## Task Management

This project uses `kb` for task tracking. Data is in ~/.kanban/ (not in this repo).
Active project: <slug>

When assigned a ticket:
1. Run `kb context <ticket-id>` and read the full output before starting
2. Run `kb move <ticket-id> in-progress`
3. Comment on the ticket as you make progress or decisions
4. Track files you modify: `kb edit <id> --add-file <paths>`
5. When done: `kb handoff <ticket-id> -m "summary of what was done, key decisions, files changed"`
6. Run `kb move <ticket-id> done`

To see current project status: `kb board` or `kb snapshot`
To see what's assigned to you: `kb list --assignee <your-name>`
```

---

## Importing from Jira

When you have access to Atlassian MCP tools, use this workflow:

1. Read the Jira ticket using MCP tools to get title, description, subtasks, acceptance criteria
2. Format the data as JSON matching the import schema above
3. Run `kb import --json '<json>'` or `kb import --file export.json`
4. The `source` field preserves the link back to the original Jira ticket

---

## Key Concepts for Agents

**Context briefing** (`kb context`): Always read this before starting a ticket. It contains everything you need — project overview, epic scope, your task details, what previous agents did on dependency tasks, and what's happening in parallel. This replaces reading the whole repo.

**Handoff notes** (`kb handoff`): Always write these when finishing a ticket. They transfer your knowledge to the next agent. Include: what was done, what files changed, key decisions, and gotchas.

**Dependencies** (`depends_on`): If your ticket depends on others, their handoff notes are automatically included in your context briefing. Check the dependency status — if a dependency isn't done yet, your ticket may be blocked.

**Comments**: Use comments for async collaboration. Humans will comment with feedback, questions, or approvals. Check the comments in your context briefing and respond to any open questions.

**Decisions log** (epics only): When a significant decision is made during an epic, update it with `kb edit E-001 --decisions "- Decision 1\n- Decision 2"`. This ensures all agents working on the epic share the same understanding.

**Project targeting**: Use `kb -P <slug>` to run any command against a specific project without switching. Useful when agents work across multiple projects.
