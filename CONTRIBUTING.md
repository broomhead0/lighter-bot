# Contributing

## Branching
- `main` is stable.
- Feature: `feat/<short-name>`
- Fix: `fix/<short-name>`
- Ops/infra: `chore/<short-name>`

## Commit style
Conventional commits (examples):
- `feat(optimizer): add OI weighting`
- `fix(ws): handle 404 fallback`
- `chore(ci): add pre-commit`

## Dev environment
```bash
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r dev-requirements.txt
pre-commit install

Running
.venv/bin/python -m core.main

Tests
.venv/bin/pytest -q

Lint/format
.venv/bin/ruff check --fix .
.venv/bin/black .

PR checklist

Tests pass, lints clean

Update config.yaml or docs if behavior changes

Include relevant logs/screens in PR
