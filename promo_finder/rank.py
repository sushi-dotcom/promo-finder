"""Step 5: combine the judge's scores into a final ranking."""

WEIGHTS = {"hook": 1.0, "cliffhanger": 1.3, "standalone": 0.8}   # cliffhangers matter most
EARLY_BONUS = 0.5          # assumption 12: new viewers start at episode 1
MAX_PER_EPISODE = 2        # assumption 13: variety in the top list


def final_score(cand, n_episodes):
    j = cand.llm
    score = sum(w * j[k] for k, w in WEIGHTS.items())
    earliness = 1 - (cand.first_episode - 1) / max(1, n_episodes - 1)
    return round(score + EARLY_BONUS * earliness, 2)


def rank(candidates, n_episodes, top=15):
    for c in candidates:
        c.final = final_score(c, n_episodes)
    ordered = sorted(candidates, key=lambda c: -c.final)
    per_episode, top_list = {}, []
    for c in ordered:
        ep = c.first_episode
        if per_episode.get(ep, 0) >= MAX_PER_EPISODE:
            continue
        per_episode[ep] = per_episode.get(ep, 0) + 1
        top_list.append(c)
        if len(top_list) >= top:
            break
    return top_list
