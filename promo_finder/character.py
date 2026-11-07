"""Step 3: Character teasers - 2-3 short moments of one main character, joined in story order.

"Main characters" = the ones with the most lines after name normalization (assumption 11).
Each moment starts on one of the character's lines and ends on a full line, so nothing is cut.
"""
import collections
import re

from .candidates import (Candidate, HOOK_TONES, HOOK_WORDS, MIN_LEN, MAX_LEN, cliff_score,
                         describe, events_between, hook_score, rules_total)

MOMENT_MIN, MOMENT_MAX = 6.0, 20.0


def main_characters(episodes, how_many=3):
    counts = collections.Counter(e.speaker for ep in episodes for e in ep.events
                                 if e.kind == "DIALOGUE")
    return [name for name, _ in counts.most_common(how_many)]


def _moment_score(line):
    """How striking is this one line? Used to choose moments, before the LLM sees them."""
    s = 0.0
    if re.search(HOOK_WORDS, line.text, re.I):
        s += 1.5
    if re.search(HOOK_TONES, line.tone, re.I):
        s += 1.0
    if "!" in line.text or line.text.rstrip().endswith(("?", "...")):
        s += 1.0
    if len(line.text.split()) <= 10:
        s += 0.5
    return s


def _moments(ep, name):
    """Short stretches in one episode that start on the character's line."""
    dialogue = [e for e in ep.events if e.kind == "DIALOGUE"]
    out = []
    for i, line in enumerate(dialogue):
        if line.speaker != name:
            continue
        t0, t1 = line.start, line.end
        for nxt in dialogue[i + 1:]:                     # add the replies that follow
            if nxt.end - t0 > MOMENT_MAX:
                break
            t1 = nxt.end
            if t1 - t0 >= MOMENT_MIN * 1.5:
                break
        if t1 - t0 >= MOMENT_MIN:
            out.append((_moment_score(line), ep.number, t0, t1, describe(line)))
    return out


def character_candidates(episodes, per_character=2, how_many=3):
    by_num = {ep.number: ep for ep in episodes}
    found = []
    for name in main_characters(episodes, how_many):
        moments = sorted((m for ep in episodes for m in _moments(ep, name)), reverse=True)
        used_eps = set()
        for _ in range(per_character):
            chosen = []
            for score, epn, t0, t1, text in moments:
                if epn in used_eps or any(abs(epn - c[1]) < 2 for c in chosen):
                    continue                             # spread across the series
                if sum(c[3] - c[2] for c in chosen) + (t1 - t0) > MAX_LEN:
                    continue
                chosen.append((score, epn, t0, t1, text))
                if len(chosen) == 3:
                    break
            total = sum(c[3] - c[2] for c in chosen)
            if len(chosen) < 2 or total < MIN_LEN:
                break
            chosen.sort(key=lambda c: (c[1], c[2]))      # play in story order
            used_eps.update(c[1] for c in chosen)
            first, last = chosen[0], chosen[-1]
            h, h_text = hook_score(events_between(by_num[first[1]], first[2], first[3]), first[2])
            c_score, c_text = cliff_score(events_between(by_num[last[1]], last[2], last[3]),
                                          by_num[last[1]], last[3])
            standalone = 2.5                             # one clear character = easy to follow
            cand = Candidate("Character", [(c[1], c[2], c[3]) for c in chosen], h, c_score,
                             standalone, rules_total(h, c_score, standalone, total),
                             h_text, c_text, character=name)
            found.append(cand)
    return found
