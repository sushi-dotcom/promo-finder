"""Find promos in a microdrama's screenplays.

Examples:
  python run.py --input "path/to/episode folder"                    # Gemini (needs GEMINI_API_KEY)
  python run.py --input "path/to/episode folder" --provider rules   # no model, works offline
  python run.py --input ... --provider openai --model <name>        # any OpenAI-compatible API
"""
import argparse
import os

from promo_finder.candidates import one_scene_candidates
from promo_finder.character import character_candidates
from promo_finder.export import export
from promo_finder.judge import Judge
from promo_finder.llm import APIConfigError, make_llm
from promo_finder.parse import load_show


def main():
    p = argparse.ArgumentParser(description="Find ranked promo clips in microdrama screenplays.")
    p.add_argument("--input", required=True, help="folder with one .txt screenplay per episode")
    p.add_argument("--provider", default="gemini", choices=["gemini", "openai", "rules"])
    p.add_argument("--model", default=None, help="model name (optional)")
    p.add_argument("--judge-top", type=int, default=30,
                   help="how many One-Scene candidates the model judges (keeps API calls low)")
    p.add_argument("--top", type=int, default=15, help="size of the final ranked list")
    p.add_argument("--batch-size", type=int, default=3,
                   help="candidates per model call (smaller = shorter replies, fewer timeouts)")
    p.add_argument("--out", default="outputs")
    args = p.parse_args()

    show = os.path.basename(os.path.normpath(args.input))
    episodes, merges = load_show(args.input)
    by_num = {ep.number: ep for ep in episodes}
    print(f"Parsed {len(episodes)} episodes of '{show}'. Name merges: {merges or 'none'}")

    one_scene = sorted((c for ep in episodes for c in one_scene_candidates(ep)),
                       key=lambda c: -c.score)[:args.judge_top]
    characters = character_candidates(episodes)
    candidates = one_scene + characters
    print(f"Candidates: {len(one_scene)} One-Scene + {len(characters)} Character")

    llm = make_llm(args.provider, args.model)
    print(f"Judging with {llm.name} ...")
    try:
        Judge(llm, show, batch_size=args.batch_size).judge_all(candidates, by_num)
    except APIConfigError as err:
        raise SystemExit(f"Stopped: {err}\nFix --model or the API key and run again.")

    from promo_finder.rank import rank
    top = rank(candidates, len(episodes), args.top)
    meta = {"show": show, "episodes": len(episodes), "judged_by": llm.name,
            "name_merges": merges, "candidates_judged": len(candidates)}
    records = export(top, candidates, meta, args.out)

    fell_back = sum(c.llm.get("judged_by") == "rules" for c in candidates)
    if args.provider != "rules" and fell_back:
        print(f"Note: {fell_back} candidates fell back to rules scores (model reply missing).")
    print(f"\nTop {min(5, len(records))} promos:")
    for r in records[:5]:
        segs = " + ".join(f"Ep{s['episode']} {s['start']}-{s['end']}" for s in r["segments"])
        print(f"  {r['rank']}. [{r['type']}] {segs} ({r['duration_s']}s) "
              f"score={r['scores']['final']}\n     why: {r['why_it_works']}")
    print(f"\nSaved {args.out}/promos.json and {args.out}/promos.csv")


if __name__ == "__main__":
    main()
