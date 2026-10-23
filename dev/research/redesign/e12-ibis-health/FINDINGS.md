# E12 — ibis project health and tacit's dependence on upstream (2026-10-23)

> The E12 subagent (Sonnet) returned this report as text, and the main session saved it here.
> Raw data, scripts and the stub experiment are in this folder; `NOTES.txt` is the index. Nothing was posted to GitHub.

## Bottom line

1. **Is there an official statement on why maintenance slowed?** Yes, but only partial ones.
   - cpcloud on discussion #11227 (2025-05-20): *"the project lost most of its full time staff in September of 2024 due to layoffs."*
   - cpcloud on issue #11604 (2025-10-14): *"I am not stopping maintenance myself, but I won't be working on Ibis full time."*
   - There has been no blog post or funding announcement. The "Who supports Ibis?" page is stale (it still says "nine full-time developers").
2. **Why was py.typed rejected?** It was never refused on request. The maintainers removed it themselves in 2023 (PR #7563) as *"a bit of a false promise"*: the codebase had 2,746 mypy errors and mypy wasn't run in CI. They then closed #6844 as "not planned". A 2025 request asking for it back got no maintainer reply.
3. **Does the proposal require upstream patches?** No.
4. **What if upstream never merges them?**
   - The runtime check still catches the one case that is missed statically.
   - Alternatively, tacit could ship a generated stub overlay (tested below).
   - Keeping ibis behind tacit's own types keeps a backend swap feasible.

## 1. Official statements and governance

**Facts:**
- **Statements from maintainers:**
  - #11227, cpcloud (2025-05-20): *"The rug has not been pulled. However … the project lost most of its full time staff in September of 2024 due to layoffs. Please get involved if you're interested!"*
  - #11604 (2025-09 to 10): the reporter said *"with @cpcloud moving to a different role it seems like day-to-day maintenance of ibis has stalled"*. cpcloud replied *"I am not stopping maintenance myself, but I won't be working on Ibis full time."* Nick Crews was nervous about being *"solely able to merge PRs"*. Deepyaman offered to help with *"smaller fixes and reviews"*.
  - #11227, Nick Crews (2026-01-27): a call for reviewers and triage help.
- **Funding:** the Voltron Data blog (2024-02-08) says ibis is *"independently governed … and not owned by Voltron Data"*, and that 4 of 5 steering committee members were Voltron Data employees. Voltron Data's November 2024 layoffs (about half of ~120 staff) were reported by The Information (paywalled; only the summary was seen). There is no fiscal sponsor such as NumFOCUS.
- **Governance:** the governance repo (github.com/ibis-project/governance) was last updated in 2024. Its steering committee lists cpcloud, jcrist, gforsyth, tswast and kszucs. Deepyaman was granted commit access on 2026-03-20 (governance issue #9).
- **Who merges now:**
  - Deepyaman made 10 of the 13 merges in 2026-10.
  - Nick Crews has merged since 2025-12.
  - gforsyth merges occasionally.
  - cpcloud's last merge was 2026-06-11.
- **Release plan:** #12102 "chore(release): 13.0.0" was opened 2026-09-04 and is still open. Releases are cut from a manual semantic-release workflow.
- **Other:**
  - The prerelease job has been failing since 2026-06-16 (#12023).
  - An AI-contribution policy (2026-02-12) auto-closes PRs the bot suspects are AI-generated.
  - Nick Crews's typing-policy poll (#11955) got no replies.

**Inference:**
- The funded team ended with the layoffs. What remains is a part-time or volunteer group.
- Nobody has declared ibis deprecated or in "maintenance mode".

## 2. Activity metrics, re-verified with bots excluded

**Releases and commits:**
- 12.0.0 is dated 2026-02-07 and there has been no release since. The 258-day gap is the longest in the project's history; the previous longest was 148 days.
- Human commits fell from 739 in Nov 2024–Oct 2025 to 162 in Nov 2025–Oct 2026, a 78% drop.
- Monthly human commits, March to September 2026: 3, 13, 15, 7, 6, 9, 6. October 2026 has 18 so far, and there was a push on 2026-10-22.
- E7 reported 87 commits since 12.0.0 and 512 in the year before. The recount gives 88 and 499; the difference comes from how bots were filtered.

**External PRs:**

| Window | Opened | Merged | Merge rate | Median time to merge |
|---|---|---|---|---|
| Year before 12.0.0 | 78 | 53 | 68% | 1.9 days |
| Since 12.0.0 | 119 | 24 | 20% | 5.9 days |

Since 12.0.0, a further 52 PRs were closed unmerged and 43 are still open. 25 PRs got no human response at all.

**Issues and backlog:**
- Issues getting a team response within 7 days fell from 64% (2024 H1) to 16% (2026 H1).
- There are 136 open PRs and 411 open issues.

**Peers** (human commits in the last 12 months; contributors with 5 or more commits):

| Project | Commits | Contributors with 5+ commits |
|---|---|---|
| ibis | 197 | 5 |
| polars | 4,720 | 42 |
| sqlglot | 2,512 | 35 |
| narwhals | 495 | 9 |
| duckdb-python | 503 | 5 |
| pandera | 309 | 8 |

**Downstream signals:**
- PyPI downloads (ClickPy) grew from 0.11M/month (2024-01) to 3.5–3.9M/month (Aug–Sep 2026). The figures include CI and mirror traffic.
- There are 159 dependents on deps.dev.
- **Google's bigframes now vendors its own copy of ibis** (`third_party/bigframes_vendored/ibis`) and no longer depends on the package. That is a precedent for forking.
- `FortnoxAB/ibis-typing` (released 2026-10-23) patches typed overloads into installed ibis files. Other users are hitting the same typing gap.

## 3. py.typed history

| Date | Event |
|---|---|
| 2023-01-20 | #5279 (tswast, Google BigQuery): request to add `py.typed`. cpcloud: *"This seems reasonable to me."* Added in PR #5304. |
| 2023-08-11 | #6844 (binste, Altair): the marker caused mypy errors in downstream projects. cpcloud: *"we're not testing mypy at the moment … it's a lot of work to add them."* |
| 2023-10-24 | gforsyth ran mypy: *"Found 2746 errors in 253 files"*. *"I don't think any of the maintainers is up for the herculean effort … My inclination is to remove the `py.typed` file."* |
| 2023-11-16 | PR #7563 removed it: *"a bit of a false promise, since Ibis is not fully typed (nor even close). Removing it so we stop causing headaches for downstream projects."* |
| 2023-12-23 | #6844 closed as not planned: *"If someone would like to push this forward, please submit incremental pull requests … Please open up bug reports for incorrect annotations as they arise!"* |
| 2025-05-02 | Marco Gorelli (narwhals) asked for the upside of type-checking ibis-based code in CI. **No maintainer reply.** |

The marker was removed because the annotations were incomplete and mypy wasn't in CI, not because the maintainers oppose typing. No condition for re-adding it has been stated. The marker is absent from both the 12.0.0 wheel and main.

## 4. Upstream typing PRs

**While cpcloud was active, typing PRs moved fast.**
- Nick Crews's #11771, #11826, #11828, #11838, #11845 and #11856 were merged between 2026-01-12 and 2026-02-04.
- External typing fixes #11665 and #11722 merged in 3 and 7 days.

**Since then, typing PRs have stalled.**
- #11966 (comparison operators): a draft with 0 reviews and a merge conflict.
- #11809 (`literal` overloads): no review since 2025-12.
- Two small external typing PRs (#12014, #12146) were auto-closed by the AI-policy bot.

**Nick Crews writes almost all the typing PRs, so he cannot also approve them.** The governance rules require an approver other than the author.

**Outlook for the two one-line fixes:** they have a realistic chance of merging, but nothing is guaranteed.

## 5. Dependence analysis

**Nothing in the proposal requires an upstream change.** E8's 185-case matrix ran on stock ibis 12.

Some things only benefit from upstream changes:

| Item | Benefit | If never merged |
|---|---|---|
| The two one-line fixes (`rich.py` mixin, `relations.py` self-import) | A raw `ir.Table` passed where a Frame is expected gets rejected statically on mypy, ty and pyrefly | Only a static miss; runtime `@step` and `cast` still catch it |
| #11966 | Fewer false positives on raw ibis code | Use Frame methods or `tc.as_ibis` |
| ibis `py.typed` | mypy users could drop `follow_untyped_imports` | Document the flag |

**Stub-overlay test** (`exp/`): a raw `ibis.table()` was passed where a Frame is expected.

| Setup | pyright | mypy | ty | pyrefly |
|---|---|---|---|---|
| Stock ibis | rejects | misses | misses | misses |
| Partial stub package (2 hand-fixed modules, about 130 lines) | rejects | misses | rejects | broken |
| Full stubgen package (161 files, about 9.7k lines, plus the 2 edits) | rejects | rejects only when placed on `mypy_path` | rejects | rejects |

Notes on the overlay:
- It is regenerable by script, but must be regenerated for every ibis release.
- It keeps ibis's existing annotation flaws.
- Mypy resolution through an installed `-stubs` package was not tested.
- **Cheaper alternative:** don't ship stubs. Rely on the runtime guard, plus a documented mypy flag.

**Exit options if ibis becomes unmaintained** (effort figures are estimates):

| Option | Effort | Notes |
|---|---|---|
| A. Pin or vendor ibis (as bigframes does) | 1–2 weeks | Keep it minimal: DuckDB plus one or two backends. |
| C. Native DuckDB/sqlglot backend behind `Frame` | 3–6 weeks | sqlglot is very active and already an ibis dependency. |
| B. Narwhals behind `Frame` | 4–8 weeks | The facade, join and aggregate code, and the SQL-style validator would need rewriting. |
| D. Polars-only | lowest implementation effort | Loses every SQL engine. |

These options assume users never touch ibis types directly. That's true for the wrapper design. With a runtime ibis subclass (E13's "thin" design), ibis is part of the user-facing API, so a swap would be costlier.

## 6. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ibis 13 breaks internals tacit relies on | medium | medium | CI against ibis `main` now; cap `ibis-framework<13` and `polars<2` |
| 13.0 slips or never ships | medium | low–medium | Pin 12; offer reviews for the #12102 release items |
| Typing fixes never merged | medium–high | low | Make no feature depend on them; review #11966 and #11809 |
| ibis effectively unmaintained | low–medium within 12 months | high | Keep users isolated from ibis types; keep a short exit-plan ADR (A, then C, then B); watch release, merge and response metrics |
| Stub overlay burden | only if adopted | low–medium | Don't adopt unless users ask for it |

**Main risk:** low velocity, not abandonment.

## 7. Facts vs inference

**Verified:**
- Releases, commit, PR and issue statistics.
- Governance and committer changes.
- py.typed history and quotes.
- The stub-overlay results.
- cpcloud's statements.

**Inferred:**
- The cause of the slowdown.
- The 12-month outlook.
- The effort estimates for the exit options.
- Why the PR acceptance rate fell.

**Not verifiable:**
- The Zulip announcement.
- cpcloud's current employer (sources conflict).
- When bigframes vendored ibis.
- The paywalled article.
- Mypy behavior with stubs installed in site-packages.
