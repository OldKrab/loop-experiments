# Results: fixed vs dynamic loading

Run on 2026-11-14 with `uv run python src/bench.py -n 3`, commit `eb0d9ec`.

- **Backend:** `http://127.0.0.1:8787/v1`, model `deepseek-flash`, temperature 0.1.
- **Task:** *"An alert fired on the payments service. Investigate, fix it, and close it out per team process."* Each run starts from a fresh copy of `demo/`.
- **Success:** decided by `src/check.py`. Tests pass, a new CI run is green, PAY-142 is `resolved` with a comment that states the root cause and cites the green run, and ALERT-7 is acknowledged with the issue key.

## Summary (means of 3 runs)

| mode | success | turns | prefix (system + tools, chars) | turn-1 input | input | cached input | uncached input | output |
|---|---|---|---|---|---|---|---|---|
| fixed | 3/3 | 15 | 20,381 | 5,284 | 161,002 | 150,016 | 10,986 | 6,409 |
| dynamic | 3/3 | 13 | 4,366 | 1,269 | 105,213 | 95,829 | 9,384 | 3,305 |

## Per run

| mode | run | success | turns | input | cached input | output | seconds |
|---|---|---|---|---|---|---|---|
| fixed | 1 | yes | 20 | 230,146 | 217,600 | 8,095 | 54 |
| fixed | 2 | yes | 15 | 145,468 | 135,040 | 5,423 | 39 |
| fixed | 3 | yes | 11 | 107,393 | 97,408 | 5,708 | 35 |
| dynamic | 1 | yes | 13 | 99,566 | 90,112 | 2,715 | 23 |
| dynamic | 2 | yes | 13 | 110,497 | 101,120 | 3,932 | 28 |
| dynamic | 3 | yes | 13 | 105,577 | 96,256 | 3,269 | 25 |

## Observations

- **Prefix size:** the prefix sent on every turn shrinks from about 5.3k to 1.3k tokens, and total input drops by about 35%. Output drops by about 50%.
- **Caching:** the prompt cache works in both modes, with 91–94% of input cached, because neither mode changes the system prompt or `tools` during a session.
- **Fixed mode varies more (11–20 turns):** with every skill inlined, the model sometimes also followed skills the task didn't need. Run 1 wrote a `postmortem-PAY-142` wiki page and opened 3 follow-up issues; run 2 opened 1 follow-up issue.
- **Dynamic mode is consistent:** every run made the same loads (`hotfix-workflow` and `payments-domain`, plus one `load_tools` call) and took 13 turns.
- **Over-loading:** in every dynamic run, `load_tools` asked for all 5 namespaces even though only `issues`, `ci` and `metrics` were used. Loading only those would save more.
- **No errors:** there were no validation or tool errors in any run.
- **Caveat:** N=3 with one model and one task, so treat the numbers as indicative.
