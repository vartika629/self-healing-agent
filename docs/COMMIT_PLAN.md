# Git Commit Plan

Make the commits **one by one**, in this order, so the history shows how the project was built.
Each step: `git add <files>` then `git commit -m "<message>"`.

| # | Files to add | Commit message |
|---|---|---|
| 1 | `.gitignore .env.example requirements.txt` | `Initial setup: requirements, gitignore and env example` |
| 2 | `executor.py` | `Add sandbox executor with timeout, temp dir, output limit and safety check` |
| 3 | `llm.py` | `Add LLM module with Gemini/Groq support and fix prompt` |
| 4 | `diff_utils.py` | `Add diff utilities to show code changes between attempts` |
| 5 | `agent.py` | `Add self-healing loop with max attempts and loop detection` |
| 6 | `demo_scripts/` | `Add broken demo scripts for live demo` |
| 7 | `app.py .streamlit/config.toml` | `Add Streamlit UI with live attempts, diff view and download` |
| 8 | `tests/ pytest.ini` | `Add pytest unit tests for executor and agent loop` |
| 9 | `README.md docs/` | `Add README, architecture diagram and project docs` |
| 10 | (your own change) | e.g. `Customize UI theme colours` or `Improve AI prompt: smallest fix rule` |

Useful commands:
- `git status` – what changed / what is staged
- `git log --oneline` – list of commits
- `git diff` – see changes before committing
- `git push` – upload commits to GitHub
