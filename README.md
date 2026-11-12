# Roblox Up-and-Coming forecast v2

`main.py` fits a smoothed place-occupancy model from the supplied chart history. It uses rank, recent rank movement, playing-count growth, and chart age to estimate each observed game's probability of occupying each top-ten place, while reserving probability for unnamed games and future churn.

Run locally with Python 3.13 and only the standard library:

```sh
MAKEFUN_INPUT_DIR=/path/to/input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

The program reads `task.json` and `history.ndjson` from the input directory and writes the task's forecast filename to the output directory.
