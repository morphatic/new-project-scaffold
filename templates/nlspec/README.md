# Tiered NLSpec Templates

These templates implement a three-tier split of the NLSpec format to reduce per-task context pressure while preserving the full-document coherence an NLSpec gives to an implementing agent.

## The tier model

Each logical spec is split across three files:

| File | Role | Load strategy |
|------|------|---------------|
| `<name>.nlspec.index.md` | Annotated table of contents — elevator pitch, pointers into the other files, 1–2 sentence summary of every section | **Always load.** Tiny (~1–2KB). |
| `<name>.nlspec.md` | **Tier 1 — Contract.** The binding, implementation-driving spec. Problem, principles, scope, architecture, data model, capability sections, cross-cutting contracts, Definition of Done. | **Always load** for implementation work. |
| `<name>.nlspec.rationale.md` | **Tier 2 — Rationale.** "Why X instead of Y" design decisions, appendices, reference catalogs, agent-discoverability meta. | **Load on demand** — when an agent hits a judgment call or needs to revisit a past decision. |

## Why split?

Monolithic NLSpecs can easily reach 60–100KB (~15–25k tokens each). Loading two specs pushes ~20% of a 200k context window before any code is read. The tier split keeps always-on context lean while keeping full rationale available when needed.

## Rules for what goes where

**Tier 1 (contract):**
- Describes behavior an implementer must produce.
- Removing it would cause the implementation to be incomplete or wrong.
- Binding, not explanatory.

**Tier 2 (rationale):**
- Explains *why* a Tier 1 decision was made, or what alternatives were rejected.
- Removing it leaves the implementation correct but leaves a later reader without historical context.
- Reference material (enumeration catalogs, parameter tables) that is *consulted*, not *read linearly*.

If a cross-cutting concern (e.g., a security constraint, observability requirement, data contract) turns out to be in Tier 2 but agents need it frequently, **promote it to Tier 1** rather than abandoning the tiered approach.

## When to use these templates

- New specs: start with all three files from day one.
- Existing monolithic NLSpecs: split when size or context pressure becomes a problem. Use the index file as the migration scaffolding.

## Filename convention

- `<name>.nlspec.md` → Tier 1 contract (preserves existing filename for continuity).
- `<name>.nlspec.rationale.md` → Tier 2.
- `<name>.nlspec.index.md` → Index.

Place all three in `plinth/specs/` (or wherever the project's NLSpecs live).
