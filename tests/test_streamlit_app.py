from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")


def analyse_view():
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["view"] = "analyse"
    return at.run()


def texts(at, kind):
    return " ".join(str(getattr(e, "value", "")) for e in getattr(at, kind))


def test_default_view_is_the_designed_site_full_screen():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    frames = at.get("iframe")
    assert len(frames) == 1 and "github.io/MigrateLens" in str(frames[0].proto)
    assert not at.selectbox  # the analysis UI is not rendered on the site view


def test_bundled_sample_renders_with_banner_and_no_exception():
    at = analyse_view()
    assert not at.exception
    assert "validated, not deployed" in texts(at, "warning")
    assert at.selectbox(key="sample").value  # a bundled sample is selected by default
    labels = [m.label for m in at.metric]
    assert {"Guardrail verdict", "Model calls", "terraform validate"} <= set(labels)
    assert len(at.tabs) == 5


def test_every_bundled_sample_renders():
    at = analyse_view()
    for name in at.selectbox(key="sample").options:
        at.selectbox(key="sample").select(name).run()
        assert not at.exception, name


def test_unverified_sample_is_not_presented_as_correct():
    at = analyse_view()
    at.selectbox(key="sample").select("sns-email-china").run()
    assert "Could not verify" in texts(at, "error")
    assert at.metric[0].value == "could not verify"


def test_url_mode_requires_input_and_a_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = analyse_view()
    at.radio(key="mode").set_value("Public GitHub URL").run()
    assert not at.exception
    assert at.button[0].disabled  # nothing typed yet, so Analyse is disabled
