"""MigrateLens demo: AWS -> Google Cloud migration copilot (Streamlit).

Bundled samples are served from recorded runs (no API calls). Live analysis of a public GitHub URL
uses the Gemini free tier and is capped per session and per day. Nothing from an analysed repo is
ever executed, and nothing is deployed to Google Cloud.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from migratelens.cache import Cache  # noqa: E402
from migratelens.throttle import DailyBudget, DailyBudgetExceeded  # noqa: E402
from migratelens.tools.github_fetch import FetchError, fetch_public_repo  # noqa: E402
from migratelens.tools.repo_reader import RepoTooLarge  # noqa: E402

RUNS_DIR = ROOT / "eval" / "runs"
DEMO_STATE = ROOT / ".migratelens" / "demo"
LIVE_RUNS_PER_DAY = 15  # whole-app daily cap on live analyses (protects the free quota)
LIVE_RUNS_PER_SESSION = 2
LIVE_CALLS_PER_DAY = 250  # model-call cap for the whole app
REPO_URL = "https://github.com/abhibarnwal707/MigrateLens"

st.set_page_config(page_title="MigrateLens", page_icon="🔭", layout="wide")


def _secret_key() -> bool:
    """Make the Gemini key available from the environment, a local .env, or Streamlit secrets."""
    load_dotenv(ROOT / ".env")  # local development only; .env is git-ignored
    if os.environ.get("GEMINI_API_KEY"):
        return True
    try:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
        return True
    except Exception:  # noqa: BLE001 - no secrets file / key not set
        return False


def _read(path: Path) -> str:
    return path.read_text() if path.exists() else ""


def sample_names() -> list[str]:
    return sorted(p.name for p in RUNS_DIR.iterdir() if (p / "result.json").exists())


def load_sample(name: str) -> dict:
    d = RUNS_DIR / name
    res = json.loads((d / "result.json").read_text())
    return {
        "source": f"recorded run of the bundled sample `{name}`",
        "result": res,
        "plan": res.get("plan") or "",
        "rejected_plan": _read(d / "plan.rejected.md"),
        "terraform": _read(d / "terraform" / "main.tf"),
        "dockerfile": _read(d / "Dockerfile"),
        "ci": _read(d / ".github" / "workflows" / "ci.yml"),
        "terraform_checked": True,
    }


def make_zip(files: dict[str, str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            if text:
                z.writestr(name, text)
    return buf.getvalue()


async def _analyse(repo: Path, out: Path):
    from migratelens.agent import AgentSession, SessionConfig
    from migratelens.pipeline import run_migration

    cfg = SessionConfig(rpm=20, daily_limit=LIVE_CALLS_PER_DAY, use_mcp=True)
    session = AgentSession(
        repo, cfg, cache=Cache(DEMO_STATE / "cache.sqlite"), state_dir=DEMO_STATE
    )
    try:
        return await run_migration(repo, out, session, validate_tf=False)
    finally:
        await session.close()


def run_live(url: str) -> dict:
    DEMO_STATE.mkdir(parents=True, exist_ok=True)
    DailyBudget(LIVE_RUNS_PER_DAY, DEMO_STATE / "runs.json").consume()  # raises when capped
    with tempfile.TemporaryDirectory() as tmp:
        repo = fetch_public_repo(url, Path(tmp) / "src")
        out = Path(tmp) / "out"
        res = asyncio.run(_analyse(repo, out))
        return {
            "source": f"live analysis of {url}",
            "result": json.loads((out / "result.json").read_text()),
            "plan": res.plan or "",
            "rejected_plan": _read(out / "plan.rejected.md"),
            "terraform": _read(out / "terraform" / "main.tf"),
            "dockerfile": _read(out / "Dockerfile"),
            "ci": _read(out / ".github" / "workflows" / "ci.yml"),
            "terraform_checked": False,
        }


def show(data: dict) -> None:
    res = data["result"]
    verified = res["verdict"] == "verified"
    st.caption(f"Source: {data['source']}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Guardrail verdict", "Verified" if verified else res["verdict"].replace("_", " "))
    c2.metric("Revisions", res["retries"])
    c3.metric("Model calls", res["llm_calls"])
    c4.metric("Tokens", f"{res['tokens']:,}")
    tf = res.get("terraform")
    if tf is not None:
        tf_label = "passes" if tf["ok"] else "fails"
    else:
        tf_label = "not run" if not data["terraform_checked"] else "n/a"
    c5.metric("terraform validate", tf_label)

    if not verified:
        st.error(
            "Could not verify this plan. The evidence checker rejected every draft, so no plan or "
            "artifacts are offered as correct. This is the guardrail working as designed."
        )
    tabs = st.tabs(["Plan", "Terraform", "Dockerfile", "CI pipeline", "Guardrail & run details"])
    with tabs[0]:
        if verified:
            st.markdown(data["plan"])
        elif data["rejected_plan"]:
            with st.expander("Last rejected draft (NOT verified, do not rely on it)"):
                st.markdown(data["rejected_plan"])
    for tab, key, lang, fname in (
        (tabs[1], "terraform", "hcl", "main.tf"),
        (tabs[2], "dockerfile", "dockerfile", "Dockerfile"),
        (tabs[3], "ci", "yaml", "ci.yml"),
    ):
        with tab:
            if data[key]:
                st.code(data[key], language=lang)
                st.download_button(f"Download {fname}", data[key], file_name=fname, key=f"dl_{key}")
            else:
                st.info("Not generated for an unverified plan.")
    with tabs[4]:
        st.write(
            f"Stop reason: `{res['stop_reason']}` · Revisions used: {res['retries']} of 2 · "
            f"First-draft violations: {res['first_draft_violations']} of "
            f"{res['first_draft_items']} items checked"
        )
        for i, rej in enumerate(res["rejections"]):
            st.markdown(f"**Rejected draft {i + 1}**")
            st.table([{"check": v["kind"], "item": v["item"], "why": v["detail"]} for v in rej])
        if not res["rejections"]:
            st.success("The first draft passed every check: no rejections.")
    if verified:
        zip_bytes = make_zip(
            {
                "plan.md": data["plan"],
                "terraform/main.tf": data["terraform"],
                "Dockerfile": data["dockerfile"],
                ".github/workflows/ci.yml": data["ci"],
            }
        )
        st.download_button(
            "Download all artifacts (.zip)", zip_bytes, "migratelens-artifacts.zip", key="dl_zip"
        )


st.title("🔭 MigrateLens")
st.write("An AWS → Google Cloud migration copilot built on Google's ADK and Gemini.")
st.warning("**Generated Terraform is validated, not deployed.** Nothing here touches Google Cloud.")
st.info(
    "Runs on the Gemini **free tier** with shared limits. Bundled samples replay recorded runs "
    f"and use no quota. Live analysis is capped at {LIVE_RUNS_PER_SESSION} runs per visitor "
    f"session and {LIVE_RUNS_PER_DAY} per day for everyone, and uses only **public** repositories "
    "(free-tier prompts may be used by Google to improve its products)."
)

with st.sidebar:
    st.header("Choose an app")
    mode = st.radio("Source", ["Bundled sample", "Public GitHub URL"], key="mode")
    st.markdown(f"[Source code & results on GitHub]({REPO_URL})")

if mode == "Bundled sample":
    names = sample_names()
    if not names:
        st.error("No recorded samples found.")
    else:
        name = st.selectbox("Sample app", names, key="sample")
        st.session_state["data"] = load_sample(name)
else:
    url = st.text_input("Public GitHub repository URL", placeholder="https://github.com/owner/repo")
    used = st.session_state.get("live_runs", 0)
    has_key = _secret_key()
    if not has_key:
        st.warning("Live analysis is unavailable: no Gemini API key is configured on this server.")
    go = st.button(
        "Analyse (uses free quota)",
        disabled=not has_key or used >= LIVE_RUNS_PER_SESSION or not url,
    )
    if used >= LIVE_RUNS_PER_SESSION:
        st.info("You have used this session's live runs. Try a bundled sample.")
    if go:
        try:
            with st.status("Fetching and analysing (about 1-3 minutes)...", expanded=True):
                st.session_state["data"] = run_live(url)
            st.session_state["live_runs"] = used + 1
        except DailyBudgetExceeded:
            st.error(
                "Today's live-analysis allowance for this demo is used up. Try a bundled sample."
            )
        except (FetchError, RepoTooLarge) as exc:
            st.error(str(exc))
        except Exception as exc:  # noqa: BLE001 - show a safe message, keep the app alive
            st.error(f"Analysis stopped: {type(exc).__name__}. Try a bundled sample.")

if st.session_state.get("data") and (mode == "Bundled sample" or go or used):
    show(st.session_state["data"])
