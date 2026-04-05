Ticketing conventions: [.claude/TICKETING.md](.claude/TICKETING.md)

## Type safety

Type safety for users is core to tacit's value proposition. When type errors
appear in usage examples, apply these rules in order:

1. **Our issue** — if the error is caused by tacit's own types, fix it.
2. **Contributable upstream fix** — if it's an upstream annotation bug we can
   fix with a small PR, document it in `dev/contributions/` and propose the fix.
3. **Minimal workaround** — if it's an upstream design limitation we can't fix,
   document the least invasive workaround for users.

We do NOT run pyright on examples. Examples stay clean and idiomatic (no
`# type: ignore`, no workarounds). Tacit's own type safety is tested via
`tests/typechecking/`, and example runtime correctness is tested via
`tests/test_examples.py`.
