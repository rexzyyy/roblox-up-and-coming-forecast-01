#!/usr/bin/env python3
"""Forecast the next up-and-coming chart from rank and player trajectories."""
import json
import math
import os
from datetime import datetime


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def forecast(history):
    """Return calibrated place probabilities and an ordered top ten."""
    usable = [r for r in history if r.get("ok") and isinstance(r.get("up_and_coming"), list)]
    if not usable:
        return {"probabilities": [], "top10": []}
    latest = usable[-1]
    now = timestamp(latest["at"])
    observations = {}
    for snap in usable:
        t = timestamp(snap["at"])
        for row in snap["up_and_coming"]:
            uid = row.get("universe_id")
            rank = row.get("rank")
            if uid is None or rank is None:
                continue
            observations.setdefault(int(uid), []).append(
                (t, float(rank), row.get("playing"))
            )

    # Estimate each game's rank after a typical multi-day chart rotation.
    # Recent ranks dominate; rank velocity and player growth add bounded nudges.
    strength = {}
    for uid, series in observations.items():
        recent = series[-5:]
        weights = [0.12, 0.16, 0.20, 0.23, 0.29][-len(recent):]
        base = sum(w * item[1] for w, item in zip(weights, recent)) / sum(weights)
        old = series[-4] if len(series) >= 4 else series[0]
        cur = series[-1]
        hours = max((cur[0] - old[0]) / 3600.0, 1.0)
        # Positive rank velocity means improvement (rank number falling).
        velocity = max(-1.2, min(1.2, (old[1] - cur[1]) / hours))
        # Use a longer player window to reduce noisy short-interval changes.
        player_growth = 0.0
        valid = [(x[0], x[2]) for x in series if isinstance(x[2], (int, float)) and x[2] > 0]
        if len(valid) >= 2:
            a, b = valid[max(0, len(valid) - 5)], valid[-1]
            span = max((b[0] - a[0]) / 3600.0, 1.0)
            player_growth = max(-0.025, min(0.025, math.log(b[1] / a[1]) / span))
        age_hours = max((now - series[0][0]) / 3600.0, 0.0)
        # A recently arrived game has room to rise; older chart residents fade gently.
        age_adjust = min(age_hours / 24.0, 10.0) * 0.10
        predicted = base - 5.0 * velocity - 170.0 * player_growth + age_adjust
        strength[uid] = predicted

    # Include every currently listed game, even if its history is sparse.
    current = latest["up_and_coming"]
    present = {int(g["universe_id"]): g for g in current if g.get("universe_id") is not None}
    for uid, game in present.items():
        strength.setdefault(uid, float(game.get("rank", 100)))

    ordered = sorted(present, key=lambda uid: strength[uid])
    probabilities = []
    # Leave a substantial shared reserve for new arrivals and unexpected movement.
    named_mass = 0.68
    for place in range(1, 11):
        # A moderately broad distribution represents the multi-day uncertainty.
        weights = []
        for uid in present:
            distance = (strength[uid] - place) / 6.2
            weights.append((uid, math.exp(-0.5 * distance * distance)))
        weights.sort(key=lambda pair: pair[1], reverse=True)
        candidates = weights[:45]
        total = sum(w for _, w in candidates)
        for uid, weight in candidates:
            p = named_mass * weight / total
            if p >= 0.00015:
                probabilities.append({"universe_id": uid, "place": place, "p": round(p, 8)})

    return {"probabilities": probabilities, "top10": ordered[:10]}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    with open(os.path.join(input_dir, "task.json"), encoding="utf-8") as handle:
        task = json.load(handle)
    history = []
    with open(os.path.join(input_dir, "history.ndjson"), encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                history.append(json.loads(line))
    result = forecast(history)
    os.makedirs(output_dir, exist_ok=True)
    with open(os.path.join(output_dir, task.get("output", "forecast.json")), "w", encoding="utf-8") as handle:
        json.dump(result, handle, separators=(",", ":"), ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
