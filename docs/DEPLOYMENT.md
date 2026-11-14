# Deployment Guide

## Option A: Streamlit Community Cloud (recommended, free)

1. Push the project to a **public** GitHub repo (see COMMIT_PLAN.md).
2. Go to <https://share.streamlit.io> and **sign in with GitHub**.
3. Click **Create app** → **Deploy a public app from GitHub**.
4. Fill in:
   - Repository: `<your-username>/self-healing-agent`
   - Branch: `main`
   - Main file path: `app.py`
5. Click **Advanced settings**:
   - Python version: **3.11** (or 3.12)
   - **Secrets** box – paste this (with your real key):
     ```toml
     LLM_PROVIDER = "gemini"
     GEMINI_API_KEY = "your-real-key-here"
     ```
6. Click **Deploy**. Wait 2–5 minutes. You get a link like
   `https://self-healing-agent-xxxx.streamlit.app`.
7. **Test the live link**: open it, check the sidebar says "AI connected", pick each
   demo script and click **Heal this script**.

Changing a secret later: app page → ⋮ menu → **Settings** → **Secrets**.
Every `git push` to `main` redeploys the app automatically.

## Option B: Hugging Face Spaces (backup)

1. Create an account at <https://huggingface.co> → **New Space**.
2. Choose the **Streamlit** template (it may be listed under Docker templates), visibility Public.
3. Upload all project files (or connect the GitHub repo).
4. Space **Settings** → **Variables and secrets** → **New secret**:
   `GEMINI_API_KEY` = your key.
5. The Space builds and gives you a public link.

## Troubleshooting

| Problem | Fix |
|---|---|
| Sidebar says "No API key" | Secret name must be exactly `GEMINI_API_KEY`; reboot the app |
| `Gemini error 404` (model not found) | Add secret `LLM_MODEL = "gemini-2.5-flash-lite"` or check model names at ai.google.dev |
| `error 429` | Free-tier rate limit – wait one minute and try again |
| `ModuleNotFoundError: streamlit` (local) | Run `pip install -r requirements.txt` |
| App crashed on Cloud | ⋮ → **Manage app** shows the logs |
