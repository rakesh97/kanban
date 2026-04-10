# kanban

Git-based project management built for AI agents and humans.

Tickets live as markdown files in a `.kanban/` directory inside your repo. No database, no web UI, no accounts — just files, a CLI, and a context protocol that makes agents effective.

## Install

```bash
cd kanban
pip install -e .
```

This gives you the `kb` command globally.

## Quick start

```bash
# initialize in any project repo
cd /path/to/your/project
kb init --name "My Project"

# create an epic
kb create epic "User Authentication" --priority high

# create tasks under the epic
kb create task "Design auth schema" --epic E-001 --priority high \
  --description "Design the database schema for users, sessions, and tokens"
kb create task "Implement JWT auth" --epic E-001 --priority high \
  --depends-on E-001-T-001
kb create task "Write auth tests" --epic E-001 \
  --depends-on E-001-T-002

# view the board
kb board

# assign work
kb assign E-001-T-001 rakesh --type human
kb assign E-001-T-002 claude --type agent

# start working
kb move E-001-T-001 in-progress
```

## Commands

| Command | Description |
|---------|-------------|
| `kb init` | Initialize `.kanban/` in the current directory |
| `kb create epic\|task\|subtask` | Create a ticket |
| `kb board` | ASCII kanban board |
| `kb list` | List tickets with filters |
| `kb show <id>` | Display ticket details |
| `kb edit <id>` | Edit ticket (flags or `$EDITOR`) |
| `kb move <id> <status>` | Change status: `backlog`, `in-progress`, `done` |
| `kb comment <id> <msg>` | Add a comment |
| `kb assign <id> <name>` | Assign to agent or human |
| `kb unassign <id>` | Remove assignment |
| `kb context <id>` | Generate agent context briefing |
| `kb handoff <id>` | Write completion/handoff notes |
| `kb snapshot` | Project-wide status summary |
| `kb import` | Import tickets from JSON |
| `kb delete <id>` | Delete a ticket |

## Ticket hierarchy

```
Epic (E-001)
  └── Task (E-001-T-001)
        └── Subtask (E-001-T-001-S-001)
```

- **Epics** group related work. They have a decisions log.
- **Tasks** are concrete units of work assigned to an agent or human.
- **Subtasks** break tasks down further.

## Statuses

- `backlog` — not started
- `in-progress` — actively being worked on
- `done` — completed

## Labels: agent vs human

Every ticket can be assigned with a type:

```bash
kb assign E-001-T-002 claude --type agent
kb assign E-001-T-001 rakesh --type human
```

Filter by assignee type:

```bash
kb list --assignee-type agent
kb board --assignee-type human
```

## Agent workflow

The core loop for AI agents:

```bash
# 1. Get briefing before starting work
kb context E-001-T-003
# outputs: project summary + epic scope + task detail + dependency handoffs

# 2. Claim the ticket
kb move E-001-T-003 in-progress

# 3. Comment as you work
kb comment E-001-T-003 "Starting implementation" --author claude --author-type agent

# 4. Track files you change
kb edit E-001-T-003 --add-file src/auth.py,src/middleware.py

# 5. When done, write handoff notes
kb handoff E-001-T-003 -m "Implemented JWT auth with RS256. Added middleware for protected routes."

# 6. Mark complete
kb move E-001-T-003 done
```

## Context system

The `kb context` command generates a focused briefing document that includes:

- **Project summary** from `.kanban/PROJECT.md`
- **Epic scope** and decisions
- **Task details** with all comments
- **Handoff notes** from dependency tasks
- **Sibling task status** so the agent knows what's happening in parallel

This solves the memory problem: agents don't read the whole repo — they get a focused briefing.

## Importing from Jira

Use `kb import` with a JSON file matching this structure:

```json
{
  "type": "epic",
  "title": "User Authentication",
  "description": "Full auth system with JWT",
  "source": "JIRA:AUTH-100",
  "priority": "high",
  "tasks": [
    {
      "title": "Design schema",
      "description": "Database schema for auth tables",
      "source": "JIRA:AUTH-101",
      "priority": "high"
    },
    {
      "title": "Implement login",
      "description": "POST /auth/login endpoint",
      "source": "JIRA:AUTH-102",
      "subtasks": [
        {
          "title": "Input validation",
          "description": "Validate email and password format"
        }
      ]
    }
  ]
}
```

```bash
kb import --file jira-export.json
# or pipe from an agent
echo '{"type":"epic","title":"Quick epic"}' | kb import
```

When using the Atlassian MCP tools, have your agent read the Jira ticket, format it as JSON, then pipe it through `kb import`.

## Directory structure

```
.kanban/
  config.yaml           # project name, default author
  PROJECT.md            # project-level context (agents read this)
  epics/
    E-001.md
  tasks/
    E-001-T-001.md
    E-001-T-002.md
  subtasks/
    E-001-T-001-S-001.md
  handoffs/
    E-001-T-001.handoff.md
  snapshots/
    2024-01-15-143022.md
```

## Adding to your project's CLAUDE.md

Add this to your repo's `CLAUDE.md` so every agent knows the protocol:

```markdown
## Task Management

This project uses kanban (.kanban/) for task tracking.

Before starting work on a ticket:
1. Run `kb context <ticket-id>` and read the output
2. Run `kb move <ticket-id> in-progress`
3. Comment on the ticket as you make progress
4. Track files you modify with `kb edit <id> --add-file <paths>`
5. When done, run `kb handoff <ticket-id> -m "summary of work done"`
6. Run `kb move <ticket-id> done`
```

## File format

Each ticket is a markdown file with YAML frontmatter:

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
files: [src/auth.py]
parent: E-001
source: JIRA:AUTH-102
created: 2024-01-15T10:30:00
updated: 2024-01-15T14:22:00
---

# Implement user authentication

## Description

Implement JWT-based authentication for the API.

## Acceptance Criteria

- [ ] Login endpoint returns JWT token
- [ ] Middleware validates token on protected routes

---

## Comments (2)

### comment::claude::agent::2024-01-15T12:00:00

Starting work on this.

### comment::rakesh::human::2024-01-15T13:00:00

Use RS256 algorithm, not HS256.
```

Files are human-readable, agent-readable, and git-friendly.
