# Results: fixed vs dynamic loading

Run on 2026-11-14 with `uv run python src/bench.py -n 3`.

- **Backend:** `http://127.0.0.1:8787/v1`, model `deepseek-flash`, temperature 0.1.
- **Task:** *"An alert fired on the payments service. Investigate, fix it, and close it out per team process."* Each run starts from a fresh copy of `demo/`.
- **Success:** decided by `src/check.py`. Tests pass, a new CI run is green, PAY-142 is `resolved` with a comment that states the root cause and cites the green run, and ALERT-7 is acknowledged with the issue key.

## Current: `load_tools(names)`, skill descriptions in both modes

### Summary (means of 3 runs)

| mode | success | turns | prefix (system + tools, chars) | turn-1 input | input | cached input | uncached input | output | input / turn |
|---|---|---|---|---|---|---|---|---|---|
| fixed | 3/3 | 14 | 21,933 | 5,639 | 136,938 | 126,379 | 10,559 | 3,799 | 9,554 |
| dynamic | 3/3 | 14 | 4,395 | 1,270 | 80,912 | 73,600 | 7,312 | 2,998 | 5,920 |

### Per run

| mode | run | success | turns | input | cached input | output | seconds | tools loaded |
|---|---|---|---|---|---|---|---|---|
| fixed | 1 | yes | 12 | 107,816 | 97,792 | 3,544 | 25 | all 20 (native) |
| fixed | 2 | yes | 15 | 140,078 | 129,280 | 3,055 | 27 | all 20 (native) |
| fixed | 3 | yes | 16 | 162,921 | 152,064 | 4,799 | 36 | all 20 (native) |
| dynamic | 1 | yes | 14 | 88,546 | 80,256 | 3,705 | 28 | 12 |
| dynamic | 2 | yes | 14 | 75,219 | 68,736 | 2,488 | 23 | 11 |
| dynamic | 3 | yes | 13 | 78,972 | 71,808 | 2,800 | 23 | 12 |

### Observations

- **Input:** with the same number of turns (14), dynamic uses 41% less total input and 38% less input per turn.
- **What dynamic loads:** every run loaded only the 2 relevant skills and 11–12 of the 20 tools, all from `metrics`, `issues` and `ci`. None came from `docs` or `deploy`.
- **Caching:** 91–92% of input was cached in both modes, because neither mode changes the system prompt or `tools` during a session.
- **Fixed mode no longer goes off task:** no postmortems and no follow-up issues. Its output fell from 6.4k to 3.8k tokens.
- **No errors:** there were no validation or tool errors in any run.
- **Caveat:** N=3 with one model and one task, so treat the numbers as indicative.

## Previous: `load_tools(namespaces)`, fixed mode without skill descriptions

| mode | success | turns | input | cached input | output |
|---|---|---|---|---|---|
| fixed | 3/3 | 15 | 161,002 | 150,016 | 6,409 |
| dynamic | 3/3 | 13 | 105,213 | 95,829 | 3,305 |

Two problems made this comparison misleading, and both are fixed in the current version:

- **Dynamic over-loaded tools.** In every run, `load_tools` asked for all 5 namespaces on turn 1, before the model had read the skill. The schemas it got back were slightly larger than the native ones (11.6k vs 10.7k chars, because of indented JSON), so from turn 2 on the per-turn input matched fixed mode. Tool loading saved nothing.
- **Fixed went off task.** Fixed mode inlined skill bodies without their descriptions, under "Follow every skill that applies", so it sometimes also ran skills the task didn't need. One run wrote a postmortem and opened 3 follow-up issues. The 35% saving came mostly from that extra work.
