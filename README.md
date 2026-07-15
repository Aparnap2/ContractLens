# ContractLens

Legal AI for M&A/vendor due diligence — extract poison-pill clauses from Indian commercial contracts, compute deterministic legal and financial risk, and populate a risk register with remediation actions.

## Architecture

```
apps/          — api (FastAPI), worker (LangGraph), web (Next.js)
packages/      — domain, providers, workflows, rules, exports, integrations
infra/         — docker, migrations, seed
tests/         — unit, integration, e2e, evals, fixtures
```

## Quick Start

```bash
docker compose up
```

See [docs/master_spec.md](docs/master_spec.md) for the full master blueprint.
