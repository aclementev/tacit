# Ticketing System

Lightweight project management for tacit, using GitHub Issues.

## Ticket types

| Type | Label | Use for |
|------|-------|---------|
| **feature** | `feature` | Work that delivers part of a milestone |
| **bug** | `bug` | Something that's broken |
| **spike** | `spike` | Time-boxed research to answer a question |

## Ticket format

Every ticket (GitHub Issue) follows this structure:

```markdown
**Milestone:** #<milestone-issue-number>
**Type:** feature | bug | spike
**Depends on:** #<issue>, #<issue> (or "none")
**Blocked by:** #<issue> (or "none")

## Description
What this ticket delivers and why.

## Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Notes
Context, references to docs, design decisions.
```

## Labels

- `feature`, `bug`, `spike` — ticket type
- `M1`, `M2`, `M3`, `M4` — milestone
- `blocked` — waiting on another ticket

## Workflow

1. Tickets start as GitHub Issues, created from the PRD (`dev/PRD.md`)
2. Each milestone is also a GitHub Issue, referencing the PRD
3. The coding agent uses **issue comments** to:
   - Document progress and decisions made during implementation
   - Flag scope changes or new information discovered
   - Link to relevant commits
4. When a ticket is done, all acceptance criteria are checked off and the
   issue is closed with a comment summarizing what was delivered
5. If a ticket needs scope change, comment explaining why before changing

## References

- PRD and milestone definitions: `dev/PRD.md`
- Testing strategy: `dev/research/TESTING.md`
- Design decisions: `dev/DESIGN.md`
- Research summary: `dev/research/SUMMARY.md`
