"""Step 2: find One-Scene promo candidates and give them a quick rules-based score.

Code does the parts code is good at: listing every possible clip, respecting length
limits, never cutting a line in half, staying inside one scene, removing overlaps.
The LLM (judge.py) later re-judges only the best few.
"""
import re
from dataclasses import dataclass, field

from .parse import Episode, fmt

MIN_LEN, MAX_LEN = 20.0, 60.0                       # assumption 7: promo length

HOOK_WORDS = (r"slap|strike|struck|betray|divorce|kill|dead|death|pregnan|secret|lie|liar|"
              r"traitor|poison|duke|identity|truth|how dare|get out|marry|married|forbid|"
              r"arrest|guilty|confess|scream|gasp|shock|reveal|blood|knife|sword|dagger|"
              r"never|how could|mine")
HOOK_TONES = (r"shock|fur|cold|cruel|sneer|gloat|stun|menac|threat|defian|seeth|horri|"
              r"desper|gasp|vicious|triumph")
HOOK_ACTIONS = r"slap|strike|shove|grab|drag|throw|collaps|point"
CLIFF_ACTIONS = (r"cut to black|abrupt|gasp|freez|stunned|appears?|enter|burst|reveal|"
                 r"discover|sees?|stumbl")


@dataclass
class Candidate:
    promo_type: str                  # "One-Scene" or "Character"
    segments: list                   # [(episode, start_sec, end_sec), ...] in playing order
    hook: float = 0.0                # rules scores (0-5 / 0-4)
    cliff: float = 0.0
    standalone: float = 0.0
    score: float = 0.0
    hook_text: str = ""
    cliff_text: str = ""
    character: str = ""              # only for Character teasers
    llm: dict = field(default_factory=dict)   # filled in by judge.py

    @property
    def duration(self):
        return sum(end - start for _, start, end in self.segments)

    @property
    def first_episode(self):
        return self.segments[0][0]

    def label(self):
        return " + ".join(f"Ep{ep} {fmt(s)}-{fmt(e)}" for ep, s, e in self.segments)


def story_events(events):
    """Events that carry the story. CAMERA lines describe shots, not plot."""
    return [e for e in events if e.kind in ("DIALOGUE", "ACTION", "SOUND")]


def describe(e):
    return f"{e.speaker}: {e.text}" if e.speaker else e.text


def hook_score(events, t0):
    """Score the first 3 seconds of a clip (assumption 8)."""
    first = [e for e in story_events(events) if e.start < t0 + 3.0 and e.kind != "SOUND"]
    best, best_text = 0.0, ""
    for e in first:
        s = 0.0
        if e.kind == "DIALOGUE":
            s += 1.0                                    # someone speaks straight away
            if "!" in e.text or e.text.rstrip().endswith("?"):
                s += 1.0
            if len(e.text.split()) <= 8:
                s += 0.5                                # short, punchy line
            if re.search(HOOK_TONES, e.tone, re.I):
                s += 1.0
        if re.search(HOOK_WORDS, e.text, re.I):
            s += 1.5
        if e.kind == "ACTION" and re.search(HOOK_ACTIONS, e.text, re.I):
            s += 1.5
        if s > best:
            best, best_text = s, describe(e)
    return min(best, 5.0), best_text[:160]


def cliff_score(events, ep: Episode, t1):
    """Score how unresolved the ending is. A music/sound cue alone does not count (assumption 9)."""
    story = [e for e in story_events(events) if e.kind != "SOUND"]
    if not story:
        return 0.0, ""
    last = story[-1]
    s = 0.0
    gap = ep.duration - t1
    if gap <= 2.0:
        s += 2.0                                        # the episode's own cliffhanger
    elif gap <= 8.0:
        s += 1.0
    if last.kind == "DIALOGUE" and last.text.rstrip().endswith(("?", "...")):
        s += 1.5
    if re.search(HOOK_WORDS, last.text, re.I):
        s += 1.0
    if re.search(CLIFF_ACTIONS, " ".join(e.text for e in story[-3:]), re.I):
        s += 1.0
    if last.kind == "DIALOGUE" and last.text.rstrip().endswith("."):
        s -= 0.5                                        # a calm statement resolves tension
    return max(0.0, min(s, 5.0)), describe(last)[:160]


def standalone_score(events, ep: Episode, t0):
    """Rough guess at 'would a stranger follow this?'. The LLM judges it properly later."""
    s = 0.0
    if t0 <= 0.5 or any(abs(sc.start - t0) < 1.0 for sc in ep.scenes):
        s += 1.5                                        # starts at a scene boundary
    speakers = {e.speaker for e in events if e.kind == "DIALOGUE"}
    if 2 <= len(speakers) <= 4:
        s += 1.5
    elif len(speakers) == 1:
        s += 0.5
    if sum(e.kind == "DIALOGUE" for e in events) >= 4:
        s += 1.0
    if ep.number > 1 and t0 < 8 and re.search(r"picks up|continues|immediately", ep.continuity, re.I):
        s -= 1.0                                        # opening straight off the last episode
    return max(0.0, min(s, 4.0))


def length_bonus(seconds):
    return 0.5 if 30 <= seconds <= 50 else (0.0 if 25 <= seconds <= 55 else -0.5)


def rules_total(hook, cliff, standalone, seconds):
    return 1.0 * hook + 1.3 * cliff + 0.8 * standalone + length_bonus(seconds)


def scene_of(ep: Episode, t):
    for sc in ep.scenes:
        if sc.start - 0.5 <= t <= sc.end + 0.5:
            return sc.number
    return None


def events_between(ep: Episode, t0, t1):
    return [e for e in ep.events if e.end > t0 and e.start < t1]


def overlaps(a: Candidate, b: Candidate, limit=0.25):
    """True if two clips share more than `limit` of the shorter one."""
    shared = 0.0
    for ea, sa, xa in a.segments:
        for eb, sb, xb in b.segments:
            if ea == eb:
                shared += max(0.0, min(xa, xb) - max(sa, sb))
    return shared > limit * min(a.duration, b.duration)


def one_scene_candidates(ep: Episode, keep=3):
    """Best few non-overlapping One-Scene clips in one episode."""
    story = story_events(ep.events)
    starts = sorted({round(e.start, 1) for e in story if e.kind != "SOUND"})
    ends = sorted({round(e.end, 1) for e in story if e.kind in ("DIALOGUE", "ACTION")}
                  | {round(ep.duration, 1)})
    found = []
    for t0 in starts:
        for t1 in ends:
            length = t1 - t0
            if not MIN_LEN <= length <= MAX_LEN:
                continue
            if ep.scenes and scene_of(ep, t0) != scene_of(ep, t1 - 0.1):
                continue                                # One-Scene means one scene
            window = events_between(ep, t0, t1)
            if any(e.kind == "DIALOGUE" and (e.start < t0 < e.end or e.start < t1 < e.end)
                   for e in window):
                continue                                # never cut a line in half
            h, h_text = hook_score(window, t0)
            c, c_text = cliff_score(window, ep, t1)
            st = standalone_score(window, ep, t0)
            found.append(Candidate("One-Scene", [(ep.number, t0, t1)], h, c, st,
                                   rules_total(h, c, st, length), h_text, c_text))
    found.sort(key=lambda c: -c.score)
    kept = []
    for c in found:
        if not any(overlaps(c, k) for k in kept):
            kept.append(c)
        if len(kept) >= keep:
            break
    return kept


def clip_text(episodes_by_number, cand: Candidate):
    """Readable script of a clip for the LLM: dialogue and actions only; no CAMERA or SOUND lines."""
    lines = []
    for i, (epn, t0, t1) in enumerate(cand.segments, 1):
        ep = episodes_by_number[epn]
        if len(cand.segments) > 1:
            lines.append(f"--- Segment {i}: Episode {epn} ---")
        for e in story_events(events_between(ep, t0, t1)):
            if e.kind == "SOUND":                  # promos carry no music; don't let the model judge it
                continue
            if e.kind == "DIALOGUE":
                tag = e.speaker + (f" ({e.tone})" if e.tone else "")
            else:
                tag = e.kind
            lines.append(f"[{fmt(e.start)}] {tag}: {e.text}")
    return "\n".join(lines)
