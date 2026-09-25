# ADR-002: Consolidate the repository around Configuration 2 digital twins

- **Status:** Accepted
- **Date:** 2026-09-26
- **Supersedes:** the scope of ADR-001 (Tier-0 software demonstrator only)

## Context

The project reached its final configuration (alternative 1, Configuration 2).
Its design changes — fill session, vent confirmation, environment check,
connection and IMD checks, DIN 70121 fallback, storage mode, closed electronics
compartment — were not reflected in the Tier-0 demonstrator, and the chemical
digital twin lived outside version control as standalone HTML files.

## Decision

- One Python package, `mpro`, with a shared `baseline.json` and four twins:
  chemical, software, control and twin services (monitoring → prescriptive, UQ).
- The software twin runs on the chemical twin plant, so mission logic and
  chemistry are exercised together.
- The public site (GitHub Pages, `docs/`) keeps the existing HMI URLs and adds
  the chemical, control and integration twins plus a hub page.
- The repository holds software and code only: no project documents, tables,
  course material, datasheets or CAD. A guard test enforces this.
- Old paths (`software_demo/`, `models/`) are removed rather than kept as shims.

## Consequences

- One baseline change reaches every twin; tests check the web pages against it.
- Scenarios in `scenarios/*.json` demonstrate each Configuration 2 change and
  run in CI.
- All values remain conceptual Tier 0–1 design values; nothing here is firmware,
  a charger implementation, a functional-safety case or test evidence.
