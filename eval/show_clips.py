"""Print the script of each ranked promo, so the hand check needs no searching in episode files.

Run from the project folder:
  python eval/show_clips.py                      # top 10 from outputs/promos.json
  python eval/show_clips.py outputs_v1/promos.json 15
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from promo_finder.parse import load_show, fmt          # noqa: E402

DATA = "data/I Married a Broken Soldier. He was a Duke"


def to_sec(s):
    m, r = s.split(":")
    return int(m) * 60 + float(r)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "outputs/promos.json"
    top = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    promos = json.load(open(path, encoding="utf-8"))["ranked_promos"][:top]
    episodes, _ = load_show(DATA)
    by_num = {ep.number: ep for ep in episodes}
    for p in promos:
        print("=" * 78)
        print(f"#{p['rank']} [{p['type']}{' / ' + p['character'] if p['character'] else ''}] "
              f"{p['duration_s']} s  scores H{p['scores']['hook']} C{p['scores']['cliffhanger']} "
              f"S{p['scores']['standalone']}  spoiler={p['spoiler_risk']}")
        print(f"  model's why: {p['why_it_works']}")
        for seg in p["segments"]:
            ep = by_num[seg["episode"]]
            t0, t1 = to_sec(seg["start"]), to_sec(seg["end"])
            print(f"\n  --- Episode {ep.number} {seg['start']}-{seg['end']} ---")
            for e in ep.events:
                if e.kind == "CAMERA" or e.end <= t0 or e.start >= t1:
                    continue
                who = e.speaker + (f" ({e.tone})" if e.tone else "") if e.speaker else e.kind
                print(f"  [{fmt(e.start)}] {who}: {e.text}")
        print()


if __name__ == "__main__":
    main()
