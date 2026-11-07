# CLAUDE.md: Promo Finder (Kuku FM AI Generalist assignment)

## The assignment
- Kuku FM recruitment task. **Deadline: Sun 8 Nov 2026, 5:00 PM IST.** Submit via placement-cell form.
- Chosen: **Problem 1, Find the Promos.** Read a microdrama's screenplays and output ranked promo
  clips (20-60 s). Per promo: episode + start/end of every segment in order, the hook, the
  cliffhanger, one line on why it works. Then rank them and check quality (where does it pick badly?).
- A good promo: hook in the first 3 s, ends on a cliffhanger, makes sense to a stranger.
- The tool only picks moments: **no editing, music or text overlays.**
- Brief rules: make assumptions instead of asking (note them in the doc); use AI freely and say
  which tools + one place they got it wrong; free tiers only; must be re-runnable on a new input in
  the interview; model must be easy to swap; **the candidate must build/write it and understand it.**
- Brief tone: about 2-3 hours, "a simple, honest submission that works and is clear about its
  limits beats a polished one that overpromises." **Do not add features beyond the task list below.**

## Deliverables
1. 2-page PDF doc. 2. Repo link (no screenplays). 3. Raw outputs folder from the full 50-episode
run, unedited (shared via Drive "anyone with the link"). 4. Optional 3-min video.

## Input data
- `data/I Married a Broken Soldier. He was a Duke/` holds 50 files `episode-NNN-Episode XXXXXXX.txt`
  (English show for US audiences). If missing, extract `%USERPROFILE%\Downloads\episodes.zip` into `data/`.
- **Confidential: never commit or upload `data/`.** It is in `.gitignore`; keep it that way.
- Format: `EPISODE LOGLINE`, `CONTINUITY NOTES`, scene blocks (heading/start/end), then CAMERA,
  ACTION, SOUND FX and dialogue blocks each with `Start: (mm:ss.s) | End: (mm:ss.s)`.
- Known glitches (already handled in parse.py): header casing differs (ep 6), timestamps step back
  under 1 s (eps 4, 12), time restarts each episode, character labels drift (LADY JULIANA/JULIANA).
- Expected parse: 50 episodes, 100 scenes, 3727 events, 1487 dialogue lines; merges:
  LADY CLARISSA, LADY JULIANA, LADY CATHERINE, THE PRIEST.

## Promo types (from the candidate's own research)
- **One-Scene teaser:** one continuous stretch of a single scene, cut at its peak.
- **Character teaser:** 2-3 short moments of one main character, in story order.
- Considered and set aside (doc only): Concept/Announcement and Atmospheric/Mood teasers, because
  they need graphics/music, which the brief excludes.

## Code (done; tested offline)
- `promo_finder/parse.py`: timeline + cautious name normalization.
- `promo_finder/candidates.py`: One-Scene candidates + rules scores.
- `promo_finder/character.py`: Character montages for the top-3 speakers.
- `promo_finder/llm.py`: providers `gemini` (key via `GEMINI_API_KEY`, sent in header),
  `openai` (any OpenAI-compatible API via `LLM_BASE_URL`, `LLM_API_KEY`), `rules` (offline).
  Default Gemini model `gemini-3.8-flash` (override: `--model` or `GEMINI_MODEL`).
  Request timeout `LLM_TIMEOUT` env var (default 300 s). 429/5xx/timeouts/connection errors: 3 tries
  with back-off, then `RuntimeError` -> that batch falls back to rules. 400/401/403/404 raise
  `APIConfigError`, which stops the whole run with a "check model name / key" message.
- `promo_finder/judge.py`: prompt, JSON validation, rules fallback, disk cache. One retry only for
  broken JSON; API/network errors skip it (already retried in llm.py). **The LLM never sets timestamps.**
- `promo_finder/rank.py`, `promo_finder/export.py`, `run.py`.
- Run: `python run.py --input "data/I Married a Broken Soldier. He was a Duke" [--provider rules] [--model NAME] [--batch-size 3]`
  (`--batch-size` = candidates per model call, default 3.)

## Assumptions (go in the doc)
1. Text only: no visuals, acting or music judged. 2. Script timestamps match the final episodes.
3. `LADY X`=`X`, `THE X`=`X` only when `X` exists; generic labels (LORD, PRIEST vs HIGH PRIEST) not merged.
4. Sub-second backward timestamp steps are noise. 5. Segments stored as (episode, start, end).
6. A new interview input uses the same format with small variations. 7. Promo 20-60 s; never cut a line.
8. Hook = line/action starting in first 3 s. 9. Ending on a music/sound cue alone is not a cliffhanger.
10. Only One-Scene and Character types built. 11. Main characters = most lines (popularity proxy).
12. Small bonus for early episodes (new viewers start at ep 1). 13. Max 2 promos per episode in top list.
14. Spoilers flagged, not removed. 15. A human editor approves final picks. 16. Cost/time figures are estimates.

## Remaining tasks, in order
1. Put episodes in `data/`; run `--provider rules`; expect top picks Ep15, Ep31, Ep43, Ep28, Ep35.
2. Gemini run (user sets `GEMINI_API_KEY` themselves). If "model not found", use `--model` with a name
   from AI Studio's Rate Limit page. If auth fails (401/403), the key format `AQ.` may need a different
   auth method: check AI Studio's "Copy cURL quickstart" (with the key removed) and adapt `GeminiLLM`.
3. Review `outputs/promos.json`: are scores sensible, are "why it works" lines specific? Fix the
   prompt only if clearly broken. Known issue: Character montages all come from ep 28+.
4. Hand check: **the candidate labels ~10 picks themselves** in `eval/check_10.csv`
   (hook y/n, cliffhanger y/n, standalone y/n, failure reason). Never fill in labels for them.
5. README final check; repo to GitHub without `data/`, `.cache/`, `venv/`; outputs to Drive.
6. Help structure the 2-page doc; the candidate writes it in their own words.

## Rules for Claude Code in this repo
- Never print, log, write or commit API keys. Keys come only from environment variables.
- Keep changes small and explain each one so the candidate can explain it in the interview.
- Don't invent results, labels, review evidence or research the candidate hasn't done.
- Log real AI mistakes in `NOTES.md` (exists) for the doc's "where the AI got it wrong" section.
  Logged so far (6): ep 6 parser bug; 12-hour plan; overrated character-name finding; CLAUDE.md
  claimed NOTES.md existed when it didn't; outdated default model (gemini-2.5-flash, 404);
  retry code ignored network timeouts.
