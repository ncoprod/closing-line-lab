.PHONY: install check test verify download features backtest select report forward score
install:
	uv sync --frozen
check:
	uv run ruff check .
	uv run ruff format --check .
test:
	uv run pytest -q
verify:
	uv run cll verify
download:
	uv run cll download
features:
	uv run cll features
backtest:
	uv run cll backtest --stage validation
select:
	uv run cll select
report:
	uv run cll report
forward:
	uv run cll forward
score:
	uv run cll score
