# Results: context compaction off vs on

## Short task

Run on 2026-11-14 with `uv run python src/bench.py --modes dynamic --compact-at 0,6000 -n 3`.

- **Backend, model, task and success criteria:** the same as in `results-dynamic-loading.md` (`deepseek-flash`, temperature 0.1, the payments alert task, judged by `src/check.py`).
- **Loading mode:** `dynamic` only.
- **Threshold:** without compaction the context peaks at about 9.5k tokens, so 6,000 tokens is a deliberately low threshold that makes compaction fire 2–3 times per run.
- **Token totals include the summary calls.** `turns` counts agent turns only.

### Summary (means of 3 runs)

| compact-at | success | turns | input | cached input | uncached input | output | input / turn | compactions | peak context |
|---|---|---|---|---|---|---|---|---|---|
| off | 3/3 | 13 | 84,429 | 77,227 | 7,202 | 2,864 | 6,332 | 0 | 9.6k |
| 6000 | 3/3 | 17 | 89,143 | 74,624 | 14,519 | 4,599 | 5,349 | 2.3 | 5.8k |

### Per run

| compact-at | run | success | turns | input | cached input | output | compactions | seconds | load_skill / load_tools |
|---|---|---|---|---|---|---|---|---|---|
| off | 1 | yes | 12 | 76,445 | 69,120 | 2,548 | 0 | 22 | 2 / 1 |
| off | 2 | yes | 16 | 102,646 | 95,232 | 3,336 | 0 | 33 | 2 / 1 |
| off | 3 | yes | 12 | 74,197 | 67,328 | 2,708 | 0 | 22 | 2 / 2 |
| 6000 | 1 | yes | 20 | 102,265 | 88,064 | 4,624 | 2 | 38 | 3 / 3 |
| 6000 | 2 | yes | 14 | 74,990 | 61,824 | 4,022 | 2 | 32 | 3 / 3 |
| 6000 | 3 | yes | 16 | 90,175 | 73,984 | 5,150 | 3 | 38 | 4 / 3 |

### Compaction calls

- **Size:** each compaction took the context from 6.0–7.0k down to 2.7–3.6k estimated tokens. Summaries were 2.0–2.8k chars (570–810 output tokens).
- **Summary calls hit the cache:** 7 calls read 45,621 input tokens, of which 40,320 (88%) were cached, because each request is the unchanged history plus one appended instruction.
- **No failures:** no nudges, no `compaction_failed`, and the backend accepted the checkpoint as a second consecutive user message.
- **Estimate accuracy:** the pre-call estimate (last usage + chars/4 of new messages) was within −10% to +3% of the reported `prompt_tokens`, with a mean error of −1%.

### Observations

- **Success is unaffected:** 3/3 in both settings. Summaries kept the ids that `check.py` needs (PAY-142, ALERT-7, CI run ids) and the skill's comment format.
- **Compaction did not save tokens here.** Total input rose 6% and output 60%, and uncached input doubled.
  - *Summary calls:* about 15k input and 1.6k output tokens per run, which is almost all of the extra output.
  - *Extra turns:* 4 more per run on average, mostly to load skills and tool schemas again after a compaction (`load_skill` 2 → 3.3 per run, `load_tools` 1.3 → 3).
  - *Cache misses:* each compaction re-prefills the new checkpoint and tail (about 2k tokens), plus the uncached part of its summary call.
- **What it did buy:** the peak context fell from 9.6k to 5.8k tokens, and input per agent turn fell 16%.
- **Why there is no saving:** compaction pays off only when many turns follow it, each re-sending about 3k fewer tokens. Here a run has 13 turns in total, and the first compaction happens around turn 7, so too few turns are left to recover the summary call and the re-loading turns. The feature tasks below test longer sessions.
- **Caveat:** N=3 with one model and one task, and the "off" runs vary from 74k to 103k input on their own, so treat the numbers as indicative.

## Feature task

Run on 2026-11-14 with `uv run python src/bench.py --task feature --modes dynamic --compact-at 0,22000,38000 -n 3 -j 9`, at the same time as the fixed-mode runs in `results-dynamic-loading.md`. Cost uses `deepseek-flash` peak prices ($0.30 uncached input, $0.006 cached input and $1.20 output per 1M tokens).

- **Task:** 4 detailed feature tickets on marshmallow 4.4.0 (`demo-feature/`), done one at a time, each with its own CI run and closing comment.
- **Judging:** hidden acceptance tests per ticket, plus the tracker state. I also read the diffs of the calibration runs, and they implement the specs.
- **Thresholds:** without compaction the context peaks at 60–70k tokens. 22,000 and 38,000 are about 35% and 60% of that.

### Summary (means of 3 runs)

| compact-at | success | turns | input | cached input | uncached input | output | peak context | compactions | cost | seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 3/3 | 69 | 2,456,918 | 2,419,968 | 36,950 | 32,502 | 63.1k | 0 | 6.46¢ | 221 |
| 38000 | 3/3 | 85 | 2,014,103 | 1,944,277 | 69,826 | 41,032 | 37.6k | 2 | 8.19¢ (+27%) | 273 |
| 22000 | 2/3 | 115 | 1,831,508 | 1,722,112 | 109,396 | 46,705 | 21.9k | 6 | 9.92¢ (+54%) | 334 |

### Per run

| compact-at | run | success | turns | input | output | peak | compactions | cost | load_skill / load_tools |
|---|---|---|---|---|---|---|---|---|---|
| off | 1 | yes | 78 | 3,015,843 | 37,628 | 69,881 | 0 | 7.49¢ | 2 / 1 |
| off | 2 | yes | 68 | 2,301,494 | 31,038 | 59,912 | 0 | 6.13¢ | 3 / 2 |
| off | 3 | yes | 62 | 2,053,416 | 28,839 | 59,626 | 0 | 5.76¢ | 3 / 2 |
| 38000 | 1 | yes | 74 | 1,666,279 | 33,972 | 37,936 | 2 | 6.90¢ | 5 / 4 |
| 38000 | 2 | yes | 90 | 2,312,781 | 45,006 | 37,507 | 2 | 9.02¢ | 4 / 3 |
| 38000 | 3 | yes | 90 | 2,063,249 | 44,118 | 37,437 | 2 | 8.64¢ | 2 / 3 |
| 22000 | 1 | no | 117 | 1,888,220 | 44,735 | 21,798 | 6 | 9.62¢ | 5 / 8 |
| 22000 | 2 | yes | 126 | 2,030,667 | 52,361 | 22,033 | 7 | 11.26¢ | 8 / 8 |
| 22000 | 3 | yes | 101 | 1,575,636 | 43,020 | 21,933 | 5 | 8.88¢ | 7 / 7 |

### Observations

- **Compaction lowers total input (−18% at 38k, −25% at 22k), but raises cost (+27%, +54%).** The input it removes is cached input, which costs 1/50 of uncached. Meanwhile, uncached input grows 1.9–3×, and output grows 26–44%.
- **The cost comes from extra turns, not from the summary calls.** Runs take 23% (38k) to 67% (22k) more turns. Counting tool calls in the logs, bash reads (`sed -n`, `grep`, `cat`) rise from about 29 per run to 40 (38k) and 48 (22k), and service calls from 32 to 39 and 51. After a compaction, the agent re-reads code it had already read, re-fetches the ticket, and re-loads skills and tool schemas.
- **A lost-process failure:** the failed 22k run implemented all 4 tickets correctly (hidden tests pass), but after a compaction it did not re-load `feature-workflow`. It closed MM-202 with a free-form comment instead of the required format. The summary had named the skill, but the agent did not load it again. Twice it also asked `call_tool` for `load_tools`, confusing the two tools.
- **Where compaction lands matters:** at 22k the agent compacts 6 times, about 1.5 times per ticket, so most compactions fall in the middle of a ticket, while the code it is editing is still needed. The finished tickets are the dead weight, and the summary cannot know that the current ticket's file reads still matter.
- **Conclusion for this harness and price list:** threshold-triggered summarization does not pay at 60–70k contexts with a 50× cache discount. Leaving it off is cheapest. It would pay with a much bigger context (relative to the window, or past the point where quality degrades), with a smaller cache discount, or if it fired at task boundaries (after a ticket is resolved) instead of mid-ticket.
- **Caveat:** N=3. The off runs alone vary from 5.8¢ to 7.5¢.

## Feature-xl task

Run on 2026-11-14 with `uv run python src/bench.py --task feature-xl --modes dynamic --compact-at 0,60000,100000 -n 3 -j 9 --max-turns 400`. Prices are as above.

- **Task:** the feature task with 10 tickets instead of 4. It adds MM-205..210: `Meta.dump_skip_none`, `validate.Each`, `fields.Interval`, `Meta.strip_strings`, `fields.Masked`, and `Schema.json_schema()`, which builds on the earlier tickets. Judging works the same way, with hidden tests for every ticket.
- **Thresholds:** two calibration runs without compaction peaked at 111k and 136k tokens, so a 150k threshold would never fire. 100k fires once, late in the run. 60k fires 2–3 times.

### Summary (means of 3 runs)

| compact-at | success | turns | input | cached input | uncached input | output | peak context | compactions | cost | seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 3/3 | 132 | 8,124,436 | 8,063,360 | 61,076 | 70,611 | 118.5k | 0 | 15.14¢ | 458 |
| 100000 | 3/3 | 120 | 5,992,119 | 5,905,493 | 86,626 | 65,815 | 99.6k | 1 | 14.04¢ (−7%) | 424 |
| 60000 | 1/3 | 157 | 5,692,713 | 5,571,584 | 121,129 | 82,185 | 59.8k | 2.7 | 16.84¢ (+11%) | 525 |

### Per run

| compact-at | run | success | turns | input | output | peak | compactions | cost | load_skill / load_tools |
|---|---|---|---|---|---|---|---|---|---|
| off | 1 | yes | 122 | 7,057,268 | 65,881 | 112,189 | 0 | 13.84¢ | 3 / 2 |
| off | 2 | yes | 120 | 6,985,787 | 66,985 | 111,584 | 0 | 13.93¢ | 2 / 2 |
| off | 3 | yes | 154 | 10,330,253 | 78,968 | 131,821 | 0 | 17.67¢ | 2 / 1 |
| 100000 | 1 | yes | 104 | 4,945,915 | 63,341 | 99,747 | 1 | 12.97¢ | 3 / 2 |
| 100000 | 2 | yes | 120 | 6,103,228 | 59,105 | 99,969 | 1 | 13.24¢ | 2 / 2 |
| 100000 | 3 | yes | 137 | 6,927,213 | 74,999 | 99,108 | 1 | 15.90¢ | 3 / 2 |
| 60000 | 1 | yes | 127 | 4,424,100 | 66,859 | 59,847 | 2 | 13.61¢ | 3 / 3 |
| 60000 | 2 | no | 149 | 5,308,197 | 93,892 | 59,544 | 3 | 18.05¢ | 3 / 2 |
| 60000 | 3 | no | 195 | 7,345,842 | 85,803 | 59,885 | 3 | 18.86¢ | 2 / 5 |

The two calibration runs without compaction (104 and 128 turns, 13.19¢ and 17.29¢, both 10/10) fall in the same range as the off row.

### Observations

- **A single late compaction at 100k is slightly cheaper, and no less reliable.** It cuts total input by 26% and cost by 7%, with 3/3 runs succeeding. The 2.1M cached tokens it removes save about 1.3¢. The extra 26k uncached tokens cost about 0.8¢, and output did not grow. This is the case predicted by the feature task: compaction pays only when the context it removes is large and many turns follow it. The difference is within the noise, though: the off runs alone range from 13.2¢ to 17.7¢.
- **At 60k the feature-task pattern returns:** more turns (+19%), double the uncached input, +11% cost, and two failures.
  - **Run 3 lost the process.** All 10 tickets pass their hidden tests. However, after a compaction the agent did not re-load `feature-workflow`, and from MM-203 on it wrote `**Summary**` headings instead of the required `Summary:` lines. The summary said "Summary/Changes/Tests/CI" but not the exact format. This is the same failure as the 22k run on the feature task.
  - **Run 2 missed one spec line.** MM-207's `Interval` works but is not in `fields.__all__`, so one hidden test fails. MM-207 was done between two compactions, after the ticket was fetched again, so this is not clearly caused by compaction.
- **The compaction cost model holds.** Compacting from C to about 20k saves roughly (C − 20k) cached tokens on each of the T turns that follow. It costs one summary call, the re-reads (uncached input and extra turns), and the risk of losing the process. At a 50× cache discount, a one-off saving needs C ≈ 100k and T ≈ 30+ to show.
- **Caveat:** N=3. A threshold that fires once per run needs more runs to separate a 7% saving from noise.
- **Working conclusion (no further runs):** compaction is taken to pay off for sessions that grow past about 150k tokens, with the threshold set near 100k or above. Below that, leaving it off is cheaper and safer.

## Re-run with skills re-loaded after compaction

Run on 2026-11-15, re-running only the configs with compaction on. Runs without compaction are unaffected by the change, so the "off" rows are the ones above.

- **The change:** the summarizer now decides which loaded skills are still in progress and ends the summary with `Load before continuing: <names>`.
- **What the harness does with it:** it puts those skill bodies into the checkpoint message, after the summary.
- **Before:** the summary only listed the loaded skills, and the model was told to load again what it needed.

| task | compact-at | success before → after | turns before → after | cost before → after | off |
|---|---|---|---|---|---|
| short | 6000 | 3/3 → 3/3 | 17 → 18 | 1.03¢ → 1.15¢ | 0.62¢ |
| feature | 38000 | 3/3 → 3/3 | 85 → 71 | 8.19¢ → 7.10¢ | 6.46¢, 69 turns |
| feature | 22000 | 2/3 → 3/3 | 115 → 102 | 9.92¢ → 9.22¢ | |
| feature-xl | 100000 | 3/3 → 3/3 | 120 → 112 | 14.04¢ → 13.80¢ | 15.14¢, 132 turns |
| feature-xl | 60000 | 1/3 → 2/3 | 157 → 150 | 16.84¢ → 17.36¢ | |

- **No process drift after compaction.** 40 of the 41 compactions wrote the reload line, and each of those named `feature-workflow` or `hotfix-workflow`. The one summary without the line came late in a run, after the last ticket. No run lost the closing-comment format, which caused two of the three earlier failures.
  - Re-loading costs 500–1,600 tokens per compaction, and the post-compaction context is not cached anyway.
- **Fewer turns.** At 38k the run is now about as long as without compaction (71 vs 69 turns), down from 85. Part of the earlier re-reading came from the agent working without its skills.
- **The one failure is not caused by compaction.** In feature-xl at 60k, run 2 wrote "MM-202 resolved" at turn 29 without calling `issues_transition`, before its first compaction at turn 54. It repeated the same skip through MM-209, so 8 tickets were left `in_progress` with correct code and comments. Later summaries carried the false "resolved" forward: the summarizer can only keep what the history says, not check it.
- **Cost.** Compaction at 100k is still slightly cheaper than off (−9%), and lower thresholds still cost more. The conclusion below is unchanged: compaction is for long sessions, with a high threshold.

## Prompt cache (question 1 of the task)

Prefix caches (vLLM, SGLang, llama.cpp, and hosted APIs) reuse a request's KV cache only up to the first token that differs from an earlier request. The harness therefore treats the request as `[tools][system][task][checkpoint][append-only turns]` and changes it only from the right:

- **Dynamic loading:** `tools` and the system prompt are built once per session and never change. Skill bodies and tool schemas arrive as tool results appended to the history, so loading something never edits the prefix.
- **Assistant messages** are stored exactly as received, so the history re-renders byte-identically on the next request.
- **Compaction is rare and large:** it fires at a threshold rather than trimming on every step, so each compaction is one planned miss, on a short post-compaction context. The tools, system prompt and task in front of the checkpoint stay byte-identical and stay cached (about 1.3k cached tokens on the first post-compaction turn in every run). The checkpoint is never edited until the next compaction.
- **The summary call itself hits the cache:** it sends the current history unchanged with the same `tools` and parameters, plus one appended instruction (88% cached here). A fresh summarization prompt that re-serializes the history would be a full miss.
- **Output capping happens at ingest:** large bash output is cut to head + tail before it enters the history, so it never has to be rewritten later.
