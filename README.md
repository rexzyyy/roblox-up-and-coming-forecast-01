# Roblox Up-and-Coming forecast

This entry estimates each game's next chart position from recent rank movement,
player-count growth, and time on the chart. It spreads each place's probability
across plausible candidates and leaves probability mass for unseen surprises.

Run locally with Python 3:

```sh
MAKEFUN_INPUT_DIR=path/to/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program reads `task.json` and `history.ndjson` from the input directory and
writes the task's forecast filename to the output directory.
