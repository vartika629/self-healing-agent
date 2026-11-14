# Presentation (10 minutes) + Demo Script (2 minutes)

## Slide outline

| # | Slide | Time | What to say |
|---|---|---|---|
| 1 | Title | 0:30 | Project name, team names, guide/teacher name |
| 2 | Problem | 1:00 | Beginners lose hours on errors. Copy-pasting errors into ChatGPT is slow and manual: copy error, paste, copy fix, run again… |
| 3 | Objective | 0:45 | Build an AI **agent** that fixes a script by itself in a loop, safely, and shows every step |
| 4 | What is an AI agent? | 1:00 | Chatbot = one answer. Agent = observes → decides → acts → checks result → repeats. Our loop: run → read error → fix → re-run |
| 5 | Architecture | 1:30 | Show the Mermaid diagram. 5 modules: app, agent, executor, llm, diff_utils |
| 6 | Safety | 1:00 | Subprocess, temp folder, 10s timeout, output limit, blocked dangerous calls, max 5 attempts, loop detection |
| 7 | Live demo | 2:00 | See demo script below |
| 8 | Version control | 1:00 | GitHub repo, commit history (`git log`), .gitignore keeps API key secret, auto-deploy on push |
| 9 | Testing & results | 0:45 | 24 pytest tests, all pass; show a table of how many attempts each demo needed (fill in from your own runs) |
| 10 | Limitations & future scope | 0:45 | Not real security (Docker next), AI can be wrong, user test cases, multi-language |
| 11 | Thank you / Q&A | 0:15 | Repo link + live link |

## 2-minute demo script

1. **(0:00)** "This is our live app on Streamlit Cloud." Point at the sidebar: "AI connected, max 5 attempts, 10-second limit."
2. **(0:15)** Pick **2. Zero Division**. "Rohan has no marks, so the average divides by zero." Click **Heal this script**.
3. **(0:35)** "Attempt 1 failed with ZeroDivisionError. The agent sent the code and error to the AI. Here is the AI's explanation, and here is the diff – green added, red removed – just like `git diff`. Attempt 2 passed."
4. **(1:00)** Show the final result: metrics, healing meter, fix history, **Download** button.
5. **(1:15)** Pick **5. Infinite Loop**. "This one never ends, so our sandbox kills it after 10 seconds and tells the AI it is probably an infinite loop." Run it.
6. **(1:40)** Pick **8. Dangerous Blocked**. Run it. "This script tries to delete a folder. Our safety check blocks it before running, and it is never sent to the AI."
7. **(1:55)** "So: automatic, safe, and every step is visible."

**Backup plan:** record your screen doing this demo the night before (phone or OBS). If Wi-Fi or the API fails, play the video.
