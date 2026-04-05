# Documentation Architecture Decisions

Decided: April 2026. Based on a spike evaluating six frameworks (Sphinx, MkDocs
Material, VitePress, Mintlify, Starlight, Docusaurus) and a structured review of
all decision branches.

## Framework: MkDocs + Material for MkDocs

Scored 9/10 in the spike. Key reasons:

- **Markdown-native** — all content is plain `.md`, no directive syntax to learn
- **Python-native** — no Node.js toolchain, stays in `uv` ecosystem
- **Good-enough autodoc** — mkdocstrings/Griffe handles tacit's `@overload`
  signatures, generics, and Google-style docstrings via AST (no import needed)
- **Best LLM story** — `mkdocs-llmstxt` generates `llms.txt` and `llms-full.txt`
  following the llmstxt.org standard
- **Agent familiarity** — FastAPI, Pydantic, Polars all use this stack

### Why not Sphinx?

Sphinx has the most powerful Python autodoc, but the configuration overhead is
disproportionate for a 4-file library. MyST directive syntax adds a learning
curve beyond plain markdown. If tacit grows to 20+ modules and needs intersphinx
linking to ibis/pandera docs, reconsider Sphinx.

### Why not JS-based frameworks?

VitePress (5/10), Starlight (7/10), Docusaurus (4/10) all lack Python autodoc
entirely. For a type-safety-focused library that needs to render `@overload`
signatures and type annotations from source, this is a dealbreaker. They also
add a Node.js toolchain to a Python project.

### Why not Mintlify?

Best-in-class LLM output but closed-source SaaS with vendor lock-in. No
self-hosting, no Python autodoc, philosophically awkward for an open-source
library.

## Decisions

### Repository layout

| Path | Content |
|------|---------|
| `docs/` | User-facing documentation (MkDocs source) |
| `dev/` | Internal docs (PRD, DESIGN.md, research, contributions) |

### Navigation structure

```
- Home (what tacit is, install, quick example)
- Why tacit (philosophy, comparisons, who it's for)
- Getting Started (iris pipeline walkthrough)
- Concepts/
    - Schemas (classes, inheritance, field types)
    - DataFrames (typed wrapper, cast vs parse, strict mode)
    - Contracts (@contract decorator, validate=True)
    - Constraints (Annotated, Check, Nullable)
- API Reference (single curated page, 5 public symbols)
- Examples/
    - Iris Pipeline
    - TPC-H Q1
```

### API reference strategy

Single curated page with explicit mkdocstrings directives for each public
symbol (`Schema`, `DataFrame`, `contract`, `Check`, `Nullable`). No per-module
auto-generation — avoids exposing private symbols.

### Docstring format

Google style. Already used in the codebase, Griffe parses it correctly. To be
formalized with ruff `pydocstyle` rules later.

### LLM-friendly output

`mkdocs-llmstxt` plugin generates `llms.txt` (index) and `llms-full.txt`
(all docs concatenated). Can add `mkdocs-llmstxt-md` later for raw `.md`
serving if needed.

### Hosting

GitHub Pages at the default `*.github.io/tacit` URL. No custom domain for now
(can add later without breaking anything).

### Deployment

GitHub Actions workflow deploys on push to `main`. Public repos get unlimited
Actions minutes. GitHub Pages has a soft limit of 10 deploys/hour.

### Dependencies

Dedicated `docs` dependency group in `pyproject.toml`, separate from `dev`.
Pinned: `mkdocs<2` (Material doesn't support MkDocs 2.0) and
`mkdocs-material<10`.

### Maintenance mode risk

Material for MkDocs entered maintenance mode November 2025. Bug/security fixes
through November 2026. Mitigation:

- Pin `mkdocs<2` and `mkdocs-material<10` to avoid breakage
- Track Zensical (Rust-core successor that reads `mkdocs.yml` natively)
- Tacit's docs are small enough that migrating to any framework is an
  afternoon's work

## Build commands

```bash
just docs-dev    # live-reloading local server
just docs-build  # production build (artifacts only, no deploy)
```
