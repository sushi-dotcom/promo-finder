# Notes: where the AI got it wrong

- **Parser dropped episode 6 scenes.** The first parser used a case-sensitive regex for scene
  headers; episode 6 uses different header casing, so its scenes were silently missed.
- **Overscoped plan.** The AI first planned a 12-hour build, while the brief asks for about 2-3 hours
  and says a simple, honest submission beats a polished one.
- **Overrated a finding when choosing the problem.** When weighing Problem 3, the AI overrated
  how important the character-name finding was.
- **Claimed notes existed that didn't.** CLAUDE.md said the three mistakes above were "already
  logged" in NOTES.md, but the file never existed until now.
- **Outdated default model name.** The AI set the default Gemini model to `gemini-2.5-flash`,
  which was outdated and returned 404. Changed the default to `gemini-3.8-flash` (still
  overridable with `--model` or `GEMINI_MODEL`).
- **Retry code ignored network timeouts.** The AI's retry logic only handled 429/5xx status
  codes, not network timeouts, so one slow reply (`ReadTimeout`, 120 s) crashed the whole
  Gemini run on the first batch. Now timeouts and connection errors are retried with back-off,
  then that batch falls back to rules; the timeout is configurable via `LLM_TIMEOUT` (default 300 s).
