.PHONY: test lint eval baseline report demo

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

eval:  ## replay-only: zero API calls, reads eval/cache.sqlite
	uv run python -m eval.run_eval --mode agent

baseline:  ## replay-only: zero API calls, reads eval/cache.sqlite
	uv run python -m eval.run_eval --mode baseline

report:
	uv run python -m eval.report

demo:
	@echo "demo arrives in Step 6"
