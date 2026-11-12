import datetime
import json
import math
import os
from collections import defaultdict


def parse_time(value):
    normalized = value.replace("Z", "+00:00")
    return datetime.datetime.fromisoformat(normalized).timestamp()


def playing_amount(game):
    raw_amount = game.get("playing")
    try:
        return max(0.0, float(raw_amount or 0))
    except (TypeError, ValueError):
        return 0.0


def feature_distance(left_features, right_features):
    scales = (7.0, 1.15, 0.42, 36.0)
    squared_distance = 0.0
    for left, right, scale in zip(left_features, right_features, scales):
        scaled_delta = (left - right) / scale
        squared_distance += scaled_delta * scaled_delta
    return squared_distance


def collect_features(reads):
    first_seen_at = {}
    feature_rows = []
    read_times = [parse_time(read["at"]) for read in reads]

    for read_index, read in enumerate(reads):
        timestamp = read_times[read_index]
        games = read.get("up_and_coming") or []
        row_features = {}

        for game in games:
            game_id = game.get("universe_id")
            if not isinstance(game_id, int):
                continue

            current_rank = float(game.get("rank") or 100)
            if game_id not in first_seen_at:
                first_seen_at[game_id] = timestamp

            observations = []
            beginning = max(0, read_index - 4)
            for prior_index in range(beginning, read_index + 1):
                prior_read = reads[prior_index]
                prior_games = prior_read.get("up_and_coming") or []
                prior_game = next(
                    (item for item in prior_games
                     if item.get("universe_id") == game_id),
                    None,
                )
                if prior_game:
                    observations.append((
                        read_times[prior_index],
                        float(prior_game.get("rank") or 100),
                        playing_amount(prior_game),
                    ))

            if len(observations) >= 2:
                first_observation = observations[0]
                last_observation = observations[-1]
                elapsed_hours = max(
                    (last_observation[0] - first_observation[0]) / 3600.0,
                    0.25,
                )
                rank_slope = (
                    last_observation[1] - first_observation[1]
                ) / elapsed_hours
                playing_growth = math.log(
                    (last_observation[2] + 20.0)
                    / (first_observation[2] + 20.0)
                ) / elapsed_hours
            else:
                rank_slope = 0.0
                playing_growth = 0.0

            age_hours = max(0.0, (timestamp - first_seen_at[game_id]) / 3600.0)
            features = (current_rank, rank_slope, playing_growth, age_hours)
            row_features[game_id] = features

        feature_rows.append(row_features)

    return feature_rows


def build_samples(reads, feature_rows):
    samples = []
    for source_index, source_read in enumerate(reads):
        source_time = parse_time(source_read["at"])
        future_indices = []

        for target_index in range(source_index + 1, len(reads)):
            hours_ahead = (
                parse_time(reads[target_index]["at"]) - source_time
            ) / 3600.0
            if hours_ahead > 96.0:
                break
            if hours_ahead >= 1.0:
                future_indices.append(target_index)

        if not future_indices:
            continue

        sample_share = 1.0 / len(future_indices)
        for target_index in future_indices:
            target_places = {
                game.get("universe_id"): int(game.get("rank") or 999)
                for game in (reads[target_index].get("up_and_coming") or [])
            }
            for game_id, features in feature_rows[source_index].items():
                target_rank = target_places.get(game_id, 999)
                label = target_rank if 1 <= target_rank <= 10 else 0
                samples.append((features, label, sample_share))

    return samples


def build_forecast(reads, task):
    feature_rows = collect_features(reads)
    samples = build_samples(reads, feature_rows)
    latest_features = feature_rows[-1] if feature_rows else {}
    if not latest_features:
        return {"probabilities": [], "top10": []}

    feature_buckets = defaultdict(list)
    for features, label, sample_weight in samples:
        bucket_key = tuple(round(value, 3) for value in features)
        feature_buckets[bucket_key].append((label, sample_weight))

    occupancy_table = []
    for bucket_key, outcomes in feature_buckets.items():
        place_counts = [0.0] * 11
        bucket_total = 0.0
        for label, sample_weight in outcomes:
            bucket_total += sample_weight
            if 1 <= label <= 10:
                place_counts[label] += sample_weight
        occupancy_table.append((bucket_key, place_counts, bucket_total))

    scored_games = []
    rows = []
    for game_id, features in latest_features.items():
        weighted_counts = [0.0] * 11
        total_support = 0.0

        for bucket_key, place_counts, bucket_total in occupancy_table:
            distance = feature_distance(features, bucket_key)
            if distance > 16.0:
                continue

            kernel_weight = math.exp(-0.5 * distance) * bucket_total
            if kernel_weight < 0.00001:
                continue

            total_support += kernel_weight
            for place in range(1, 11):
                weighted_counts[place] += (
                    kernel_weight
                    * place_counts[place]
                    / max(bucket_total, 1e-12)
                )

        place_probs = []
        for place in range(1, 11):
            prior_rate = 0.085 if place <= 3 else 0.095
            probability = (
                weighted_counts[place] + 1.8 * prior_rate
            ) / (total_support + 1.8)
            place_probs.append(probability)

        scored_games.append((game_id, features, place_probs))

    shrink_factor = 0.76
    for place_index in range(10):
        leaders = sorted(
            scored_games,
            key=lambda game_row: game_row[2][place_index],
            reverse=True,
        )[:16]
        for game_id, features, place_probs in leaders:
            probability = min(0.35, place_probs[place_index] * shrink_factor)
            rows.append({
                "universe_id": game_id,
                "place": place_index + 1,
                "p": round(probability, 8),
            })

    expected_places = []
    for game_id, features, place_probs in scored_games:
        top_ten_chance = sum(place_probs)
        expected_place = (
            sum((index + 1) * place_probs[index] for index in range(10))
            + 15.0 * max(0.0, 1.0 - top_ten_chance)
        )
        expected_places.append((expected_place, features[0], game_id))

    top10 = [game_id for _, _, game_id in sorted(expected_places)[:10]]
    return {"probabilities": rows, "top10": top10}


def main():
    input_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    output_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    task_path = os.path.join(input_dir, "task.json")
    with open(task_path, encoding="utf-8") as task_file:
        task = json.load(task_file)

    history_path = os.path.join(input_dir, "history.ndjson")
    reads = []
    with open(history_path, encoding="utf-8") as history_file:
        for line in history_file:
            if line.strip():
                reads.append(json.loads(line))

    window = task["window"]
    forecast = build_forecast(reads, task)
    os.makedirs(output_dir, exist_ok=True)
    output_name = task.get("output", "forecast.json")
    output_path = os.path.join(output_dir, output_name)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(forecast, output_file, separators=(",", ":"), sort_keys=True)
        output_file.write("\n")


if __name__ == "__main__":
    main()
