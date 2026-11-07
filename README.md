# Promo Finder

Reads a microdrama's screenplays and returns a ranked list of promo clips (20-60 s), each with
its segments and timestamps, its hook, its cliffhanger and one line on why it works.

Two promo types:
- **One-Scene teaser** - one continuous stretch of a single scene, cut at its peak.
- **Character teaser** - 2-3 short moments of one main character, in story order.

## Run it

```bash
pip install -r requirements.txt

# with Gemini (free key from Google AI Studio)
export GEMINI_API_KEY="your-key"          # Windows PowerShell: $env:GEMINI_API_KEY="your-key"
python run.py --input "path/to/episode folder"

# without any model (rules only, works offline)
python run.py --input "path/to/episode folder" --provider rules
```

The input folder holds one `.txt` screenplay per episode. Results go to `outputs/promos.json`
and `outputs/promos.csv`. Model replies are cached in `.cache/`, so re-runs are free.

Options: `--batch-size N` sets how many candidates go in one model call (default 3; smaller
means shorter replies and fewer timeouts). The `LLM_TIMEOUT` env var sets how long to wait for
a reply (default 300 s). Timeouts and rate limits are retried, then that batch falls back to
rules; a wrong model name or key (400/401/403/404) stops the run with a clear message.

## Swap the model

- Different Gemini model: `--model <name>` (or set `GEMINI_MODEL`). Default: `gemini-3.8-flash`.
- Any OpenAI-compatible API (Groq, OpenAI, a company endpoint): set `LLM_BASE_URL`,
  `LLM_API_KEY`, then `python run.py --input ... --provider openai --model <name>`.
- Something else: add one class with a `complete(prompt) -> str` method in
  `promo_finder/llm.py` and register it in `make_llm()`.

## How it works

1. `parse.py` - screenplay files -> clean timeline; fixes header casing, small backward
   timestamp steps, and characters under two labels ("LADY JULIANA" -> "JULIANA").
2. `candidates.py` - every 20-60 s One-Scene clip that stays in one scene and never cuts a
   line; quick rules score (a music cue alone is not a cliffhanger).
3. `character.py` - Character teasers for the 3 characters with the most lines.
4. `judge.py` - the model scores hook, cliffhanger and standalone (1-5) and writes the
   hook, cliffhanger and "why it works" lines. It never sets timestamps. Broken replies
   are retried once, then fall back to the rules score. The model doesn't see SOUND/music
   lines: the scripts' own music cues say "cliffhanger", which inflated its scores.
5. `rank.py` - weighted score + small bonus for early episodes, max 2 promos per episode.
6. `export.py` - JSON + CSV.

## Quality check

The top 10 promos were judged by hand: 8 of 10 were postable. The 2 failures were slow pacing
and too much back-story, which the model doesn't score. The full sheet is in the Drive folder
(https://drive.google.com/drive/folders/1e50rYsLz5rnknPyFOoUW3kG_kftpYZ2c?usp=sharing).

## Final run

Gemini's free daily limit ran out, so the final run used Groq through the OpenAI-compatible
provider (`LLM_BASE_URL=https://api.groq.com/openai/v1`, `LLM_API_KEY`):

```bash
python run.py --input "path/to/episode folder" --provider openai --model openai/gpt-oss-120b
```

In the Drive folder, `outputs/` is the final run; `outputs_v1/` is an earlier run from before
the SOUND fix (see "How it works", step 4).

## Limits

Text only (no visuals, acting or music); Character teasers pick the most-speaking characters,
not necessarily the most popular; rules-only scores are rough.

The screenplays are not included in this repo.
