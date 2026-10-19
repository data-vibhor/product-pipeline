.PHONY: lint security test check
lint:
	uv run ruff check .
security:
	uv run bandit -q -r pipeline
test:
	uv run pytest -q
check: lint security test
