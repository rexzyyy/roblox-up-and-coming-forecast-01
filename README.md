# Roblox Up-and-Coming Forecast

A deterministic Python 3.13, standard-library-only forecast based on recent chart ranks and player-count trajectories. It writes the probability forecast and ordered top ten to the output directory.

Run locally with `MAKEFUN_INPUT_DIR=/path/to/input MAKEFUN_OUTPUT_DIR=/path/to/output python3 main.py`. The input directory must contain `task.json` and `history.ndjson`.
