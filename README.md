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

## Swap the model

- Different Gemini model: `--model <name>` (or set `GEMINI_MODEL`).
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
   are retried once, then fall back to the rules score.
5. `rank.py` - weighted score + small bonus for early episodes, max 2 promos per episode.
6. `export.py` - JSON + CSV.

## Quality check

The top 10 promos were judged by hand: 8 of 10 were postable. The 2 failures were slow pacing
and too much back-story, which the model doesn't score. The full sheet is in the Drive folder
(link: TODO).

## Limits

Text only (no visuals, acting or music); Character teasers pick the most-speaking characters,
not necessarily the most popular; rules-only scores are rough.

The screenplays are not included in this repo.
