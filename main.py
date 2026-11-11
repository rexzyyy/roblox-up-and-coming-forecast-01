import json
import math
import os
from datetime import datetime


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def load_history(path):
    rows = []
    with open(path, "r", encoding="utf-8") as source:
        for line in source:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def observations(history):
    games = {}
    for snapshot in history:
        stamp = parse_time(snapshot["at"])
        for game in snapshot.get("up_and_coming") or []:
            uid = game.get("universe_id")
            if not isinstance(uid, int):
                continue
            games.setdefault(uid, []).append((stamp, game.get("rank"), game.get("playing")))
    return games


def predicted_ranks(history):
    latest = history[-1]
    latest_time = parse_time(latest["at"])
    seen = observations(history)
    weights = (0.12, 0.16, 0.20, 0.23, 0.29)
    predictions = {}
    for game in latest.get("up_and_coming") or []:
        uid = game.get("universe_id")
        rank = game.get("rank")
        history_rows = seen.get(uid, [])
        if not isinstance(uid, int) or not isinstance(rank, (int, float)):
            continue
        valid = [(t, r, p) for t, r, p in history_rows if isinstance(r, (int, float))]
        if len(valid) < 2:
            predictions[uid] = float(rank)
            continue
        recent = valid[-5:]
        recent_weights = weights[-len(recent):]
        weight_total = sum(recent_weights)
        strength = sum(float(row[1]) * w for row, w in zip(recent, recent_weights)) / weight_total
        latest_row = valid[-1]
        velocity = 0.0
        if len(valid) >= 5:
            older = valid[-5]
            hours = max((latest_row[0] - older[0]) / 3600.0, 1.0)
            velocity = max(-1.2, min(1.2, (float(older[1]) - float(latest_row[1])) / hours))
        growth = 0.0
        if len(valid) >= 5:
            older = valid[-5]
            old_playing, new_playing = older[2], latest_row[2]
            if isinstance(old_playing, (int, float)) and isinstance(new_playing, (int, float)) and old_playing > 0 and new_playing > 0:
                hours = max((latest_row[0] - older[0]) / 3600.0, 1.0)
                growth = max(-0.025, min(0.025, math.log(new_playing / old_playing) / hours))
        first_seen = valid[0][0]
        age_days = max(0.0, (latest_time - first_seen) / 86400.0)
        age_adjust = min(1.0, 0.10 * age_days)
        predictions[uid] = strength - 5.0 * velocity - 170.0 * growth + age_adjust
    return predictions


def kernel(distance, width):
    return math.exp(-0.5 * (distance / width) ** 2)


def make_forecast(history):
    predictions = predicted_ranks(history)
    ordered = sorted(predictions, key=lambda uid: (predictions[uid], uid))
    probabilities = []
    width = 7.0
    mass = 0.681
    for place in range(1, 11):
        candidates = sorted(ordered, key=lambda uid: (abs(predictions[uid] - place), predictions[uid], uid))[:60]
        raw = [(uid, kernel(predictions[uid] - place, width)) for uid in candidates]
        total = sum(value for _, value in raw)
        if total <= 0:
            continue
        for uid, value in raw:
            probability = mass * value / total
            if probability >= 0.00015:
                probabilities.append({"universe_id": uid, "place": place, "p": round(probability, 10)})
    return {"probabilities": probabilities, "top10": ordered[:10]}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    with open(os.path.join(input_dir, "task.json"), "r", encoding="utf-8") as task_file:
        task = json.load(task_file)
    history = load_history(os.path.join(input_dir, "history.ndjson"))
    forecast = make_forecast(history)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, task.get("output", "forecast.json"))
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(forecast, output_file, separators=(",", ":"), ensure_ascii=False)
        output_file.write("\n")


if __name__ == "__main__":
    main()
