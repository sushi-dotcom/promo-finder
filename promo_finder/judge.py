"""Step 4: the LLM judges promo candidates. Code keeps control of all timestamps.

The model only returns scores and short text. It never chooses clip boundaries, so it
cannot point at a moment that does not exist in the script.
"""
import hashlib
import json
import os
import re

from .candidates import clip_text

PROMO_TYPES = """Promo types:
- One-Scene teaser: one continuous stretch of a single scene, cut right at its peak, context withheld.
- Character teaser: 2-3 short moments built around one character, who they are and what they face."""

PROMPT = """You are a promo editor for a vertical microdrama app. Promos are 20-60 second clips
posted on Instagram/TikTok/YouTube to win NEW viewers who have never seen the show.

A good promo:
1. Hook: the first 3 seconds stop the scroll (a slap, a reveal, a shocking line).
2. Cliffhanger: it ends on an unresolved moment, so the viewer must tap to find out.
3. Standalone: someone who has never seen the show can follow it.

{types}

Show: {show}

Judge each candidate below. Use only what is in the script. Be strict: 5 is rare.
Return ONLY a JSON list, one object per candidate, with exactly these keys:
"id" (same id as given), "hook" (1-5), "cliffhanger" (1-5), "standalone" (1-5),
"hook_moment" (the opening moment, max 15 words), "cliffhanger_moment" (the final moment, max 15 words),
"why_it_works" (one line, max 25 words), "main_weakness" (one line, max 20 words),
"spoiler_risk" ("low", "medium" or "high": does it give away a major twist?)

{candidates}"""

KEYS_INT = ("hook", "cliffhanger", "standalone")
KEYS_TEXT = ("hook_moment", "cliffhanger_moment", "why_it_works", "main_weakness")


def _candidate_block(i, cand, eps_by_num):
    loglines = "; ".join(f"Ep{ep}: {eps_by_num[ep].logline}"
                         for ep in dict.fromkeys(e for e, _, _ in cand.segments))
    extra = f", about {cand.character}" if cand.character else ""
    return (f"### Candidate id={i} | type: {cand.promo_type}{extra} | "
            f"{cand.duration:.0f} s\nEpisode summary: {loglines}\nScript:\n"
            f"{clip_text(eps_by_num, cand)}\n")


def _parse_reply(text, ids):
    """Pull the JSON list out of a reply and keep only well-formed entries."""
    if not text:
        return {}
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    data = json.loads(text)
    if isinstance(data, dict):                     # some models wrap the list
        data = next((v for v in data.values() if isinstance(v, list)), [data])
    good = {}
    for item in data:
        try:
            i = int(item["id"])
            if i not in ids:
                continue
            scores = {k: max(1, min(5, int(item[k]))) for k in KEYS_INT}
            texts = {k: str(item.get(k, ""))[:200] for k in KEYS_TEXT}
            risk = str(item.get("spoiler_risk", "low")).lower()
            good[i] = {**scores, **texts,
                       "spoiler_risk": risk if risk in ("low", "medium", "high") else "low"}
        except (KeyError, ValueError, TypeError):
            continue                               # skip a malformed entry, keep the rest
    return good


def rules_judgement(cand):
    """Fallback when there is no model, or the model fails: map rules scores to 1-5."""
    return {"hook": max(1, min(5, round(1 + cand.hook * 0.8))),
            "cliffhanger": max(1, min(5, round(1 + cand.cliff * 0.8))),
            "standalone": max(1, min(5, round(1 + cand.standalone))),
            "hook_moment": cand.hook_text, "cliffhanger_moment": cand.cliff_text,
            "why_it_works": "Rules-based pick: strong opening line and unresolved ending.",
            "main_weakness": "Not checked by a model; context and clarity unverified.",
            "spoiler_risk": "unknown", "judged_by": "rules"}


class Judge:
    def __init__(self, llm, show_name, cache_dir=".cache", batch_size=5):
        self.llm, self.show, self.batch = llm, show_name, batch_size
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _ask(self, prompt):
        """Call the model, using a disk cache so re-runs are free and repeatable."""
        key = hashlib.sha256(f"{self.llm.name}\n{prompt}".encode()).hexdigest()[:24]
        path = os.path.join(self.cache_dir, f"{key}.txt")
        if os.path.exists(path):
            return open(path, encoding="utf-8").read()
        reply = self.llm.complete(prompt)
        if reply is not None:
            open(path, "w", encoding="utf-8").write(reply)
        return reply

    def judge_all(self, candidates, eps_by_num):
        for start in range(0, len(candidates), self.batch):
            batch = candidates[start:start + self.batch]
            ids = set(range(len(batch)))
            prompt = PROMPT.format(types=PROMO_TYPES, show=self.show,
                                   candidates="\n".join(_candidate_block(i, c, eps_by_num)
                                                        for i, c in enumerate(batch)))
            results = {}
            for attempt in range(2):                   # one retry for broken JSON
                try:
                    results = _parse_reply(self._ask(prompt if attempt == 0 else
                                                     prompt + "\n\nReturn valid JSON only."), ids)
                    break
                except json.JSONDecodeError as err:     # broken reply: ask once more
                    print(f"  model problem on batch {start // self.batch + 1}: {err}")
                except RuntimeError as err:             # API/network already retried in llm.py
                    print(f"  model problem on batch {start // self.batch + 1}: {err}")
                    break
            for i, cand in enumerate(batch):
                if i in results:
                    cand.llm = {**results[i], "judged_by": self.llm.name}
                else:
                    cand.llm = rules_judgement(cand)
        return candidates
