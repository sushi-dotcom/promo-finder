"""Step 6: write the results as JSON (full detail) and CSV (easy to open in a spreadsheet)."""
import csv
import json
import os
from datetime import datetime

from .parse import fmt


def promo_record(rank, c):
    j = c.llm
    return {
        "rank": rank,
        "type": c.promo_type,
        "character": c.character or None,
        "segments": [{"episode": ep, "start": fmt(s), "end": fmt(e)} for ep, s, e in c.segments],
        "duration_s": round(c.duration, 1),
        "hook": j.get("hook_moment", ""),
        "cliffhanger": j.get("cliffhanger_moment", ""),
        "why_it_works": j.get("why_it_works", ""),
        "main_weakness": j.get("main_weakness", ""),
        "spoiler_risk": j.get("spoiler_risk", ""),
        "scores": {"hook": j["hook"], "cliffhanger": j["cliffhanger"],
                   "standalone": j["standalone"], "final": c.final},
        "judged_by": j.get("judged_by", ""),
    }


def export(top, all_judged, meta, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    records = [promo_record(i, c) for i, c in enumerate(top, 1)]
    best_by_type = {}
    for t in ("One-Scene", "Character"):
        ranked = sorted((c for c in all_judged if c.promo_type == t), key=lambda c: -c.final)
        best_by_type[t] = [promo_record(i, c) for i, c in enumerate(ranked[:3], 1)]
    payload = {"meta": {**meta, "generated_at": datetime.now().isoformat(timespec="seconds")},
               "ranked_promos": records, "best_by_type": best_by_type}
    with open(os.path.join(out_dir, "promos.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out_dir, "promos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["rank", "type", "character", "segments", "duration_s", "hook", "cliffhanger",
                    "why_it_works", "main_weakness", "spoiler_risk", "hook_score",
                    "cliffhanger_score", "standalone_score", "final_score", "judged_by"])
        for r in records:
            segs = " + ".join(f"Ep{s['episode']} {s['start']}-{s['end']}" for s in r["segments"])
            w.writerow([r["rank"], r["type"], r["character"] or "", segs, r["duration_s"],
                        r["hook"], r["cliffhanger"], r["why_it_works"], r["main_weakness"],
                        r["spoiler_risk"], r["scores"]["hook"], r["scores"]["cliffhanger"],
                        r["scores"]["standalone"], r["scores"]["final"], r["judged_by"]])
    return records
