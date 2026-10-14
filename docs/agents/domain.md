# Domain Docs

## Layout

This repo uses a single context:

- `GLOSSARY.md` at the repo root
- Architecture decision records in `docs/adr/`

## Before exploring

Read `GLOSSARY.md` and any ADRs relevant to the area being explored.

If these files do not exist, proceed silently. The domain-modeling
skill creates them lazily when terms or decisions get resolved.

## Use the glossary's vocabulary

Use glossary terms when naming domain concepts in issues, proposals,
hypotheses, and tests. If a needed concept is absent, reconsider the
term or note the gap for domain-modeling.

## Flag ADR conflicts

Explicitly surface any proposal that contradicts an existing ADR,
identifying the ADR and why the decision may deserve reopening.
