.PHONY: test lint eval baseline demo

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check .

eval:
	@echo "eval harness arrives in Step 5"

baseline:
	@echo "baseline arrives in Step 5"

demo:
	@echo "demo arrives in Step 6"
