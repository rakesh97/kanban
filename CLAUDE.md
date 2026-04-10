# kanban - Development Guide

## What this is

A CLI tool (`kb`) for git-based project management. Tickets are markdown files in `.kanban/` directories. Zero external dependencies beyond Python 3.8+.

## Project structure

```
kb/
  __init__.py   - version
  models.py     - Ticket and Comment dataclasses
  store.py      - file I/O, frontmatter parsing, ID generation
  board.py      - ASCII kanban board rendering
  context.py    - agent context briefing, handoffs, snapshots
  cli.py        - argparse CLI with all commands
```

## Key design decisions

- **Zero dependencies**: no PyYAML, no click — only Python stdlib. Frontmatter is parsed with a custom parser in store.py.
- **Files are the database**: every ticket is a `.md` file. The file format is the API.
- **IDs are hierarchical**: E-001, E-001-T-001, E-001-T-001-S-001. Zero-padded to 3 digits.
- **Frontmatter is simple YAML subset**: `key: value` and `key: [list, items]`. No nested objects.

## Running locally

```bash
pip install -e .
kb --help
```

## Testing changes

After editing, test with:
```bash
cd /tmp && mkdir test-project && cd test-project
kb init --name "Test"
kb create epic "Test Epic" --priority high
kb create task "Test Task" --epic E-001 -d "A test task"
kb board
kb show E-001-T-001
kb comment E-001-T-001 "test comment" --author dev --author-type human
kb context E-001-T-001
kb move E-001-T-001 done
kb snapshot
```
