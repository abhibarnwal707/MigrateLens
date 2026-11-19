.PHONY: test lint eval baseline report demo site site-serve

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
	uv run streamlit run app/streamlit_app.py

site:  ## rebuild site/data.json and site/data.js from the eval results
	uv run python site/build_data.py

site-serve:
	uv run python -m http.server 8000 -d site
