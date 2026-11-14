"""
app.py - The Streamlit web interface.

Run locally with:   streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

# ---- Load API keys from Streamlit secrets (used on Streamlit Cloud) -------
# Locally you can use a .env file instead (see .env.example).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    for _k in ("LLM_PROVIDER", "LLM_MODEL", "GEMINI_API_KEY", "GROQ_API_KEY"):
        if _k in st.secrets and not os.getenv(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass  # no secrets file - that's fine when running locally with .env

from agent import Attempt, HealResult, heal  # noqa: E402
from llm import get_model, get_provider, is_configured  # noqa: E402

DEMO_DIR = Path(__file__).parent / "demo_scripts"

st.set_page_config(page_title="Self-Healing Script Agent", page_icon="🩹", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_demos() -> dict[str, str]:
    demos = {}
    for f in sorted(DEMO_DIR.glob("*.py")):
        label = f.stem.split("_", 1)[-1].replace("_", " ").title()
        demos[f"{f.stem.split('_')[0]}. {label}"] = f.read_text(encoding="utf-8")
    return demos


def status_badge(a: Attempt) -> str:
    r = a.result
    if r.success:
        return "✅ Passed"
    if r.blocked:
        return "🛑 Blocked for safety"
    if r.timed_out:
        return "⏱️ Timed out (infinite loop?)"
    return f"❌ {r.error_type or 'Error'}"


def render_attempt(a: Attempt, expanded: bool = False) -> None:
    title = "Original script" if a.number == 1 else f"Fix #{a.number - 1}"
    with st.expander(f"Attempt {a.number} - {title} - {status_badge(a)}", expanded=expanded):
        if a.explanation:
            st.info(f"🤖 **AI explanation:** {a.explanation}")
        if a.diff:
            st.markdown(f"**What changed** (🟩 +{a.lines_added} added, 🟥 -{a.lines_removed} removed)")
            st.code(a.diff, language="diff")

        left, right = st.columns(2)
        with left:
            st.markdown("**Code (this version)**")
            st.code(a.code, language="python", line_numbers=True)
        with right:
            st.markdown("**Result**")
            if a.result.stdout:
                st.caption("Output")
                st.code(a.result.stdout, language="text")
            if a.result.success:
                st.success(f"Ran successfully in {a.seconds}s")
            else:
                st.caption("Error / traceback")
                st.code(a.result.error_text or "(no error text)", language="text")


def render_summary(res: HealResult, max_fixes: int) -> None:
    st.divider()
    st.subheader("Final result")
    if res.success:
        st.success(f"🎉 SUCCESS - {res.stop_reason}")
    else:
        st.error(f"⚠️ NOT FIXED - {res.stop_reason}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", "Healed" if res.success else "Failed")
    c2.metric("AI fixes used", f"{res.fixes_used} / {max_fixes}")
    c3.metric("Total runs", len(res.attempts))
    c4.metric("Time taken", f"{res.total_seconds}s")

    # "Healing meter": fewer fixes needed = higher score.
    if res.success:
        score = 1.0 - (res.fixes_used / (max_fixes + 1))
        st.progress(score, text=f"Healing efficiency: {int(score * 100)}% "
                                "(fewer attempts = better)")

    for hint in res.import_hints:
        st.warning(f"📦 {hint}")

    # Fix history log
    st.markdown("**Fix history log**")
    st.dataframe(
        [
            {
                "Attempt": a.number,
                "Result": status_badge(a),
                "Lines +/-": f"+{a.lines_added} / -{a.lines_removed}" if a.number > 1 else "-",
                "AI explanation": a.explanation or "(original script)",
            }
            for a in res.attempts
        ],
        hide_index=True,
    )

    st.markdown("**Final code**")
    st.code(res.final_code, language="python", line_numbers=True)
    st.download_button(
        "⬇️ Download fixed script",
        data=res.final_code,
        file_name="fixed_script.py",
        mime="text/x-python",
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

demos = load_demos()

with st.sidebar:
    st.header("⚙️ Settings")
    provider = get_provider()
    if is_configured():
        st.success(f"AI connected: **{provider}** (`{get_model(provider)}`)")
    else:
        st.error(
            f"No API key for **{provider}**.\n\n"
            "Add `GEMINI_API_KEY` to your `.env` file (local) or to "
            "Secrets (Streamlit Cloud). See README."
        )
    max_fixes = st.slider("Max AI fix attempts", 1, 8, 5)
    timeout = st.slider("Time limit per run (seconds)", 2, 20, 10)
    st.divider()
    st.markdown(
        "**How it works**\n\n"
        "1. Run the script in a sandbox\n"
        "2. Read the error (traceback)\n"
        "3. Ask the AI for the smallest fix\n"
        "4. Apply it and run again\n"
        "5. Repeat until it works or the limit is hit"
    )
    st.caption("🛡️ Dangerous code (deleting files, shell commands, network) is blocked.")


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------

st.title("🩹 Self-Healing Script Agent")
st.write("Give it a **broken Python script**. The agent runs it, reads the error, "
         "asks an AI to fix it, and keeps trying until the script works.")

if "code" not in st.session_state:
    st.session_state.code = next(iter(demos.values()), "")


def _load_demo():
    st.session_state.code = demos[st.session_state.demo_choice]
    st.session_state.pop("result", None)


src1, src2 = st.columns([1, 1])
with src1:
    st.selectbox("Pick a ready-made broken script", list(demos), key="demo_choice",
                 on_change=_load_demo)
with src2:
    uploaded = st.file_uploader("...or upload your own .py file", type=["py"])
    if uploaded is not None and st.session_state.get("uploaded_name") != uploaded.name:
        st.session_state.code = uploaded.read().decode("utf-8", errors="replace")
        st.session_state.uploaded_name = uploaded.name
        st.session_state.pop("result", None)

st.text_area("...or paste / edit the code here", key="code", height=260)

run = st.button("🚀 Heal this script", type="primary", disabled=not is_configured())

if run:
    st.session_state.pop("result", None)
    st.subheader("Live attempts")
    with st.spinner("Agent is working... (run → read error → ask AI → fix → run again)"):
        result = heal(
            st.session_state.code,
            max_fixes=max_fixes,
            timeout=timeout,
            on_attempt=lambda a: render_attempt(a, expanded=True),
        )
    st.session_state.result = result
    st.session_state.result_max = max_fixes
    render_summary(result, max_fixes)

elif "result" in st.session_state:
    res: HealResult = st.session_state.result
    st.subheader("Attempts")
    for a in res.attempts:
        render_attempt(a, expanded=(a is res.attempts[-1]))
    render_summary(res, st.session_state.get("result_max", max_fixes))
