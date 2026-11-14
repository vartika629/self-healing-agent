# Likely Viva Questions (with short answers)

### About the project
**1. What does your project do?**
It takes a broken Python script, runs it, reads the error, asks an AI for a fix, applies it and runs again – in a loop until the script works or we hit 5 attempts.

**2. Why is it an "agent" and not just a chatbot?**
A chatbot gives one answer and stops. Our agent acts on its own in a loop: it runs code, observes the result, decides the next step and checks whether its fix worked – without a human copying and pasting.

**3. How is this different from pasting the error into ChatGPT?**
It is automatic (no copy-paste), it actually runs and verifies every fix, it keeps trying with the history of failed fixes, it shows a diff of every change, and it is safe (sandbox + blocked code).

**4. Explain the flow / architecture.**
`app.py` (UI) → `agent.py` (loop) → `executor.py` (safety check + run in subprocess) → if it fails, `llm.py` sends code + traceback to Gemini → `diff_utils.py` shows the change → loop again.

**5. What is a traceback?**
The error report Python prints when a program crashes: which file and line failed and the error type (e.g. `ZeroDivisionError: division by zero`). The agent sends it to the AI as the "clue".

### Safety
**6. How do you run unknown code safely?**
Five layers: (1) static check with Python's `ast` module that blocks dangerous calls like `os.system`, `shutil.rmtree`, network modules, `eval`; (2) a separate subprocess, so a crash cannot crash our app; (3) a temporary folder that is deleted after; (4) a 10-second timeout; (5) an output size limit.

**7. Is your sandbox 100% secure?**
No, it is best-effort. Someone could hide dangerous code (e.g. build the name from strings). Real isolation needs Docker or a virtual machine – that is in our future scope.

**8. Why not install missing packages automatically?**
Installing packages runs someone else's code on our machine – a security risk. So we only *suggest* `pip install` and let the user decide.

### The loop
**9. Why can LLM agents loop forever? How do you stop it?**
The AI can keep making wrong fixes, repeat the same fix, or go back and forth between two versions. We stop with: max 5 attempts, a "same code" check, a cycle check (we hash every version we tried), and a timeout on every run.

**10. How do you handle an infinite loop in the user's script?**
The subprocess has a 10-second timeout. When it is killed we tell the AI "timeout – probably an infinite loop", so it looks for a loop condition that never becomes false.

**11. What if the AI's "fix" removes the bug by deleting the code or the assert?**
Our prompt forbids weakening asserts and asks for the smallest change. But it is a real limitation: "runs without error" does not always mean "correct". User-written tests would make this stronger.

### AI / prompt
**12. Which LLM do you use and why?**
Google Gemini 2.5 Flash on the free tier (Groq as a backup). It is free, fast and good at code. The API key is read from an environment variable / Streamlit secrets – never written in the code.

**13. What is in your prompt (prompt design)?**
A system prompt with rules: smallest fix, keep prints, fix loop conditions for timeouts, never weaken asserts, no dangerous code, and a strict reply format (EXPLANATION + one code block) so our code can parse it. We also send the history of failed fixes so the AI does not repeat them.

### Version control & deployment
**14. How did you use Git and GitHub?**
We built the project in small steps with meaningful commits (setup → executor → llm → agent → UI → tests → docs). `.gitignore` keeps `.env` (our API key) out of GitHub. Streamlit Cloud redeploys automatically on every `git push`.

**15. How did you test it?**
24 pytest unit tests for the executor (errors, timeout, blocking, truncation) and the loop (success, max attempts, same-code stop, cycle detection, AI errors). The loop tests use a **fake AI**, so they run without internet or an API key.

### Bonus questions
- *What is `.env` / why not hardcode the key?* Anyone who sees the repo could steal and misuse the key.
- *What is a diff?* The lines added (+) and removed (−) between two versions – the same idea as `git diff`.
- *What does `git commit` vs `git push` do?* Commit saves a snapshot on your computer; push uploads commits to GitHub.
