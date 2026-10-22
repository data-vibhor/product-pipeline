# product-pipeline

Idea to deployed app, driven by free and open-source LLMs. A human approves the brief and PRD; everything after is automated and gated by tests.

## Flow

brief -> PRD -> build -> review -> test -> test-fix -> deploy-kit -> push to a separate product repo -> CI -> Render.

## Commands

Run with `uv run python -m pipeline <command> <run_id>`:

brief, prd, revise, build, review, issues, test, test-fix, deploy-kit, fix, run-all, approve, status.

## Checks before any commit

    uv run ruff check .
    uv run bandit -q -r pipeline
    uv run pytest -q

See RULES.md for the working rules and what each stage reads and writes.
