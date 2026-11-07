"""Step 1: turn microdrama screenplay files into a clean, time-sorted timeline.

Handles the glitches found in the Kuku input pack:
  * header casing differs between episodes ("Scene heading" vs "SCENE HEADING")
  * timestamps sometimes step backwards by under a second  -> events are sorted
  * time restarts at 00:00 every episode                    -> segments keep their episode number
  * one character under two labels ("LADY JULIANA" / "JULIANA") -> normalize_names()
"""
import glob
import os
import re
from dataclasses import dataclass, field

TS = r"(\d+):(\d+(?:\.\d+)?)"          # mm:ss or mm:ss.s

# Labels that are not characters. Extra spellings make the parser tolerant of a new show.
NON_DIALOGUE = {"CAMERA": "CAMERA", "ACTION": "ACTION",
                "SOUND FX": "SOUND", "SFX": "SOUND", "MUSIC": "SOUND"}

# Title prefixes we may drop, but only when the bare name also exists (see normalize_names).
TITLES = ("LADY ", "LORD ", "SIR ", "MISS ", "MRS. ", "MR. ", "DUKE ", "DUCHESS ")


def to_sec(mm: str, ss: str) -> float:
    return int(mm) * 60 + float(ss)


def fmt(sec: float) -> str:
    """Seconds -> 'mm:ss.s' (the screenplay's own format)."""
    return f"{int(sec // 60):02d}:{sec % 60:04.1f}"


@dataclass
class Event:
    kind: str       # DIALOGUE | ACTION | CAMERA | SOUND
    speaker: str    # character name for dialogue, "" otherwise
    tone: str       # parenthetical such as "Shaken, Whispering"
    start: float
    end: float
    text: str


@dataclass
class Scene:
    number: int
    heading: str
    start: float
    end: float


@dataclass
class Episode:
    number: int
    logline: str
    continuity: str
    scenes: list = field(default_factory=list)
    events: list = field(default_factory=list)
    duration: float = 0.0


SCENE_RE = re.compile(r"SCENE (\d+)\s*\nSCENE HEADING:\s*(.*)\nSCENE START:\s*" + TS +
                      r"\s*\nSCENE END:\s*" + TS, re.I)
BLOCK_RE = re.compile(r"^\*\*(.+?):\*\*\s*\nStart:\s*\(" + TS + r"\)\s*\|\s*End:\s*\(" + TS +
                      r"\)\s*\n(.*?)(?=\n\s*\n|\Z)", re.S | re.M)


def parse_episode(path: str, fallback_number: int) -> Episode:
    text = open(path, encoding="utf-8").read()
    m = re.search(r"episode-(\d+)", os.path.basename(path), re.I)
    number = int(m.group(1)) if m else fallback_number

    def header(key):
        h = re.search(rf"^{key}:\s*(.*)$", text, re.M | re.I)
        return h.group(1).strip() if h else ""

    ep = Episode(number, header("EPISODE LOGLINE"), header("CONTINUITY NOTES"))

    for s in SCENE_RE.finditer(text):
        ep.scenes.append(Scene(int(s[1]), s[2].strip(), to_sec(s[3], s[4]), to_sec(s[5], s[6])))

    for b in BLOCK_RE.finditer(text):
        label, tone = b[1].strip(), ""
        t = re.match(r"(.*?)\s*\((.*)\)$", label)          # "JULIANA (Shaken)" -> name + tone
        if t:
            label, tone = t[1].strip(), t[2].strip()
        label = " ".join(label.upper().split())
        kind = NON_DIALOGUE.get(label, "DIALOGUE")
        line = " ".join(b[6].split()).strip('"')
        ep.events.append(Event(kind, label if kind == "DIALOGUE" else "", tone,
                               to_sec(b[2], b[3]), to_sec(b[4], b[5]), line))

    ep.events.sort(key=lambda e: (e.start, e.end))      # tolerate small backwards steps
    ends = [s.end for s in ep.scenes] + [e.end for e in ep.events]
    ep.duration = max(ends) if ends else 0.0
    return ep


def normalize_names(episodes):
    """Merge labels that are clearly the same character. Returns {old_label: new_label}.

    Rules (cautious on purpose: a wrong merge is worse than a missed one):
      * "THE PRIEST" -> "PRIEST"            if "PRIEST" exists
      * "LADY JULIANA" -> "JULIANA"         if "JULIANA" exists
      * a bare generic label like "LORD" is never merged into anyone.
    """
    labels = {e.speaker for ep in episodes for e in ep.events if e.kind == "DIALOGUE"}
    mapping = {}
    for lab in labels:
        for prefix in ("THE ",) + TITLES:
            bare = lab[len(prefix):]
            if lab.startswith(prefix) and bare in labels:
                mapping[lab] = bare
                break
    for ep in episodes:
        for e in ep.events:
            if e.speaker in mapping:
                e.speaker = mapping[e.speaker]
    return mapping


def load_show(folder: str):
    """Parse every episode file in a folder, in episode order, with names normalized."""
    files = sorted(glob.glob(os.path.join(folder, "*.txt")))
    if not files:
        raise FileNotFoundError(f"No .txt screenplay files found in {folder}")
    episodes = sorted((parse_episode(f, i + 1) for i, f in enumerate(files)),
                      key=lambda ep: ep.number)
    empty = [ep.number for ep in episodes if not ep.events]
    if empty:
        print(f"Warning: no timed lines found in episode(s) {empty}; check their format.")
    merges = normalize_names(episodes)
    return episodes, merges


if __name__ == "__main__":
    import sys
    eps, merges = load_show(sys.argv[1])
    print(f"{len(eps)} episodes, {sum(len(e.events) for e in eps)} events, "
          f"{sum(e.kind == 'DIALOGUE' for ep in eps for e in ep.events)} dialogue lines, "
          f"{sum(len(ep.scenes) for ep in eps)} scenes")
    print("Name merges:", merges)
