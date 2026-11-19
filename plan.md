# MigrateLens: Build Plan

A step-by-step plan for building MigrateLens, a Google ADK and Gemini migration copilot that moves AWS apps to Google Cloud. It is built and hosted entirely for **free**.

Each step has three parts:
- **Build**: the code and docs that get written in the repo.
- **You do**: actions only you can take (accounts, keys, reviews, commits), with links.
- **Accept**: the command or check that proves the step is done.

At the end of each step, you review the work and commit it yourself.

---

## Cost rules (apply to every step)

| Rule | What it means |
|---|---|
| No billing, no card | Never add a credit card or enable billing on any Google Cloud project. If any page asks for a card, stop. |
| Gemini free tier only | Use an API key from Google AI Studio. Free-tier prompts may be used by Google to improve products, so use only public code. |
| Terraform is never applied | Run only `terraform init -backend=false` and `terraform validate`. No cloud credentials needed. |
| Docker runs locally only | `docker build` and `docker run` on your Mac. Nothing is pushed to a cloud registry. |
| Free hosting only | Streamlit Community Cloud or a Hugging Face Space. Not Cloud Run. |
| Public data only | Sample apps are public, permissively licensed repos. Never employer code. |

---

## Step 0: Your one-time setup (≈ 30–45 min)

This step is all **you do**. Nothing gets built in the repo until it's finished.

| # | Task | Where | Notes |
|---|---|---|---|
| 0.1 | Install Homebrew (if you don't have it) | https://brew.sh | Mac package manager, used for the installs below. |
| 0.2 | Install Python 3.11+ | `brew install python@3.12` or https://www.python.org/downloads/ | Check with `python3 --version`. |
| 0.3 | Install `uv` (fast Python env and package manager) | https://docs.astral.sh/uv/getting-started/installation/ | `brew install uv`. Optional; plain `pip` + `venv` also works. |
| 0.4 | Install Terraform CLI | https://developer.hashicorp.com/terraform/install | `brew tap hashicorp/tap && brew install hashicorp/tap/terraform`. Only `validate` is used. |
| 0.5 | Install Docker (local only) | Docker Desktop: https://www.docker.com/products/docker-desktop/ (free for personal use) **or** Colima (open source): https://github.com/abiosoft/colima | Check with `docker run hello-world`. |
| 0.6 | Install the GitHub CLI (optional) | https://cli.github.com | Lets you create the repo from the terminal: `gh repo create`. |
| 0.7 | Create a Gemini API key (**free, no card**) | https://aistudio.google.com/apikey | Sign in with a personal Google account. Do **not** link a billing account. |
| 0.8 | Check the current free-tier model and limits | https://ai.google.dev/gemini-api/docs/rate-limits and https://ai.google.dev/gemini-api/docs/pricing | Note the Flash-class model name, RPM, TPM and RPD. These go into `docs/FREE_TIER.md`. |
| 0.9 | Read the free-tier data terms | https://ai.google.dev/gemini-api/terms | Confirms why only public code is used. |
| 0.10 | Put the key in your shell (never in a file that gets committed) | Your terminal | Add `export GEMINI_API_KEY="..."` to `~/.zshrc`, or put it in a local `.env` (git-ignored). **Don't paste the key into chat.** |
| 0.11 | Create an empty **public** GitHub repo called `MigrateLens` | https://github.com/new | Public, so GitHub Actions and Streamlit Cloud are free. Don't add a README; the repo will have one. |
| 0.12 | Connect the local repo to GitHub | Your terminal | `git remote add origin https://github.com/<you>/MigrateLens.git` |

**Accept:** `python3 --version`, `terraform version`, `docker run hello-world` and `echo ${GEMINI_API_KEY:+set}` all work.

---

## Step 1: Scaffold and free-tier plumbing

**Build**
- Repo layout from the brief: `migratelens/`, `eval/`, `app/`, `tests/`, `docs/`.
- `pyproject.toml` (deps: `google-adk`, `google-genai`, `mcp`, `pytest`, `ruff`, `streamlit`, `python-hcl2`, `pyyaml`), ruff and pytest config.
- `Makefile` with `test`, `lint`, `eval`, `baseline` and `demo` targets.
- `.gitignore` covering `.env`, `.venv`, cache DB and `.terraform/`.
- `migratelens/cache.py`: a SQLite response cache keyed by hash(prompt, model, tool args).
- `migratelens/throttle.py`: an RPM throttle, exponential backoff on 429 errors, and a daily-budget counter that stops before the limit.
- `migratelens/llm.py`: a thin Gemini client wrapper that uses the cache and throttle.
- `.github/workflows/ci.yml`: lint and tests on GitHub Actions, using recorded fixtures (no API key in CI).
- `docs/FREE_TIER.md`: the model name and limits from step 0.8, with the date checked.

**You do**
- Confirm the model name and limits you saw on the rate-limits page.
- Run the one-line Gemini smoke test twice.

**Accept:** `make test` and `make lint` pass; `python -m migratelens.llm "say hi"` calls the API on the first run and answers from the cache on the second.

**Docs to check before coding:**
- Gemini Python SDK (`google-genai`): https://googleapis.github.io/python-genai/
- Gemini API docs: https://ai.google.dev/gemini-api/docs
- GitHub Actions for Python: https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python

---

## Step 2: Deterministic AWS detector (no LLM)

**Build**
- `migratelens/tools/repo_reader.py`: read-only `list_files` and `read_file`. Rejects repos over 5 MB of text, skips binaries, never executes anything.
- `migratelens/tools/detector.py`: finds AWS usage with `file:line` evidence:
  - `boto3`/`botocore` clients and resources (S3, SQS, SNS, DynamoDB, Lambda, Secrets Manager, SES, …)
  - AWS SDK imports in JS and Java
  - `serverless.yml`, CloudFormation templates, Terraform `aws_*` resources
  - `docker-compose` services (e.g. localstack), Dockerfiles
  - env vars such as `AWS_REGION` and `S3_BUCKET`
  - possible secrets, reported as "possible secret in file X" **without the value**
- Output: JSON `[{service, evidence: [{file, line, snippet}], confidence}]`.
- Small fixture repos under `tests/fixtures/` and their unit tests.

**You do:** nothing yet (precision and recall on the real apps happen after Step 5's sample apps exist).

**Accept:** `make test` passes the detector tests on the fixtures.

**Reference:** boto3 service list: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/index.html

---

## Step 3: Mapping table and generators

**Build**
- `migratelens/data/mapping.yaml`: the single source of truth for AWS → GCP mappings. Each row has the target, a trade-off note, a migration risk and a docs link:
  - S3 → Cloud Storage · SQS → Pub/Sub · SNS → Pub/Sub · DynamoDB → Firestore / Bigtable · Lambda → Cloud Run functions · ECS/Fargate → Cloud Run · Secrets Manager → Secret Manager · CloudWatch → Cloud Logging / Monitoring · IAM roles → service accounts · RDS → Cloud SQL · SES → (no direct equivalent; flag it) · ECR → Artifact Registry
- `migratelens/tools/mapper.py`: looks up only from the YAML (it never invents a mapping).
- `migratelens/tools/generators.py`: template-based Terraform (Cloud Run service, service account, Pub/Sub, GCS, Secret Manager, least-privilege IAM bindings), a Dockerfile and a GitHub Actions workflow (lint, test, build; the deploy step is commented out). Gemini fills in only the app-specific values.
- A script that runs `terraform init -backend=false && terraform validate` on the generated output.

**You do**
- Skim `mapping.yaml` and check that the trade-offs read correctly to you (it's your name on the repo).

**Accept:** generated Terraform passes `terraform validate` on at least two apps; the generated Dockerfile builds locally (`docker build`) for at least one.

**Docs to check:**
- Official AWS ↔ GCP service comparison: https://cloud.google.com/docs/get-started/aws-azure-gcp-service-comparison
- Terraform Google provider: https://registry.terraform.io/providers/hashicorp/google/latest/docs
- Cloud Run Terraform resource: https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service
- IAM roles reference: https://cloud.google.com/iam/docs/understanding-roles

---

## Step 4: ADK agent, MCP tools and guardrail

**Build**
- `migratelens/mcp_server.py`: a read-only MCP server exposing `list_files`, `read_file`, `detect_aws`, `map_service` and the generators.
- `migratelens/agent.py`: the ADK root agent. Its instructions are to inventory, map, plan and generate, to always call tools instead of guessing, and to cite evidence as `file:line`. It connects to the MCP server, with direct function tools as a fallback for tests.
- **Plan format** (Markdown): inventory with evidence · mapping table · target architecture · risks and unknowns · rollout and rollback · IAM least-privilege notes · artifacts list. No dollar estimates.
- `migratelens/guardrail.py`, **in code**:
  - every AWS service named must be in the detector inventory,
  - every GCP resource named must be in `mapping.yaml`,
  - every cited file path must exist,
  - on failure it sends the specific errors back for revision (max 2 retries), then returns "could not verify" with a rejection list.
- A bounded loop with caps on iterations, tokens and wall time, and an explicit `stop_reason`.
- Run traces saved as JSONL (this also enables `make replay` later).

**You do**
- Run one end-to-end example and read the plan. Does it sound like something you'd defend in an interview?

**Accept:** an end-to-end run on one sample app produces a plan and artifacts; a unit test shows the guardrail rejecting a plan with an invented service.

**Docs to check:**
- Google ADK (Python): https://google.github.io/adk-docs/
- ADK + MCP tools: https://google.github.io/adk-docs/tools/mcp-tools/
- ADK GitHub: https://github.com/google/adk-python
- MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
- MCP spec: https://modelcontextprotocol.io

---

## Step 5: Evaluation harness (the credibility step)

**Build**
- `eval/apps/`: 6–8 small public AWS apps, each pinned to a commit hash, with the license recorded in `eval/apps/README.md`. Hand-written fixtures are labelled **synthetic**.
- `eval/truth/<app>.json`: a **draft** of the ground truth (services, correct GCP mapping, 3–6 must-mention risks), marked `"human_reviewed": false`.
- `eval/metrics.py`: service precision and recall · mapping accuracy · invented-resource rate (before retries) · risk coverage (rubric or a logged LLM judge) · Terraform validate pass rate · mean tokens, wall time and retries.
- `eval/baseline.py`: the same Gemini model with the repo concatenated into one prompt, and no tools or guardrail.
- `eval/run_eval.py`: runs both side by side, with bootstrap CIs given the small n.
- `docs/RESULTS_SUMMARY.md`: every number with its reproduce command, including any place the agent does **not** beat the baseline.

**You do (important)**
- Help pick sample apps. Search for candidates at:
  - https://github.com/aws-samples (MIT-0 / Apache-2.0, a good source)
  - https://github.com/search?q=boto3+sqs+language%3APython&type=repositories
  - https://github.com/serverless/examples
- **Review each `eval/truth/*.json` yourself**, then flip it to `"human_reviewed": true`. Results only count once you've done this.
- Spread eval runs across days if the daily free quota is hit (the cache keeps finished work).

**Accept:** `make eval` and `make baseline` both re-run fully from the cache with **zero** API calls, and `RESULTS_SUMMARY.md` lists every result with its command.

**Reference:** choosealicense.com for checking licenses: https://choosealicense.com/licenses/

---

## Step 6: Demo, docs and resume numbers

**Build**
- `app/streamlit_app.py`: pick a bundled sample app or paste a public GitHub URL (size-limited). It shows the evidence-linked plan, Terraform, Dockerfile, CI file and guardrail verdict, with download buttons, a rate-limit notice, a daily request cap and the banner **"Generated Terraform is validated, not deployed."** The bundled samples run from the cache, so visitors don't burn your quota.
- `README.md`: problem, Mermaid architecture diagram, how to run it free, results table (matching `RESULTS_SUMMARY.md`), honest limitations and how to reuse the platform parts.
- `docs/ARCHITECTURE.md`: how another team could reuse the tools, guardrail, cache, throttle and eval harness for a different agent.
- `docs/RESUME_NUMBERS.md`: measured numbers only, each with its source command, plus a "can say / must not say" list.

**You do**
1. Push the repo to GitHub (`git push -u origin main`).
2. Deploy on **Streamlit Community Cloud** (free, no card): https://share.streamlit.io → "New app" → pick the repo → main file `app/streamlit_app.py`.
   - Docs: https://docs.streamlit.io/deploy/streamlit-community-cloud
   - Add `GEMINI_API_KEY` under **App settings → Secrets**: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management
   - *Alternative:* a Hugging Face Space (Streamlit SDK, free CPU): https://huggingface.co/new-space · docs: https://huggingface.co/docs/hub/spaces-overview
3. Open the demo URL in a private/incognito window to confirm it works logged out.
4. Paste the demo URL into the README and the GitHub repo "About" box.
5. Write your resume bullets using **only** the numbers in `RESUME_NUMBERS.md`.

**Accept:** the demo URL works logged out, and the README results match `RESULTS_SUMMARY.md`.

---

## Optional extras (only after Step 6)

- `make replay`: re-run the agent from recorded JSONL model replies with no API calls.
- A CI regression suite of 10–15 cases from recorded fixtures.
- A second target cloud (e.g. Azure) behind the same mapping interface, if quick.

---

## Free tools and services used

| What | Service | Cost | Link |
|---|---|---|---|
| LLM | Gemini API free tier (AI Studio key) | Free, rate-limited | https://aistudio.google.com |
| Agent framework | Google ADK | Open source | https://google.github.io/adk-docs/ |
| Tool protocol | MCP Python SDK | Open source | https://github.com/modelcontextprotocol/python-sdk |
| IaC check | Terraform CLI (validate only) | Free | https://developer.hashicorp.com/terraform/install |
| Containers | Docker Desktop (personal) / Colima | Free | https://www.docker.com/products/docker-desktop/ |
| Code hosting + CI | GitHub public repo + Actions | Free for public repos | https://github.com |
| Demo hosting | Streamlit Community Cloud | Free, no card | https://share.streamlit.io |
| Demo hosting (alt) | Hugging Face Spaces (CPU basic) | Free | https://huggingface.co/spaces |

---

## Your checklist at a glance

- [ ] Step 0: tools installed, Gemini key created (no billing), public GitHub repo created
- [ ] Step 1: confirm free-tier limits, run smoke test twice, commit
- [ ] Step 2: commit
- [ ] Step 3: sanity-read `mapping.yaml`, commit
- [ ] Step 4: read one end-to-end plan, commit
- [ ] Step 5: help pick sample apps, **review every ground-truth file**, commit
- [ ] Step 6: push, deploy on Streamlit Cloud, add secret, test logged out, write resume bullets
