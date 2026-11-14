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
- **Why there is no saving:** compaction pays off only when many turns follow it, each re-sending about 3k fewer tokens. Here a run has 13 turns in total, and the first compaction happens around turn 7, so too few turns are left to recover the summary call and the re-loading turns. The long task below shows that it does.
- **Caveat:** N=3 with one model and one task, and the "off" runs vary from 74k to 103k input on their own, so treat the numbers as indicative.

## Long task

Run on 2026-11-14 with `uv run python src/bench.py --task long --modes dynamic --compact-at 7000,12000 -n 3 -j 6`. The "off" rows are the dynamic runs from the fixed-vs-dynamic measurement on the same task, run a few minutes earlier (`results-dynamic-loading.md`).

- **Task:** three critical payments alerts at once (`demo-long/`): the currency bug, a refund cap that ignores earlier refunds, and VAT truncated instead of rounded. The VAT alert has no issue, so the agent must create one. Success requires all three incidents closed out per the hotfix workflow.
- **Thresholds:** without compaction the context peaks at 15–19k tokens (mean 16.7k). 7,000 and 12,000 are about 40% and 70% of that.
- **Shape:** the agent fixes all three bugs in one pass and then closes out each issue, so a run takes 16–26 turns rather than three times the short task's 13.

### Summary (means of 3 runs)

| compact-at | success | turns | input | cached input | uncached input | output | input / turn | compactions | peak context |
|---|---|---|---|---|---|---|---|---|---|
| off | 3/3 | 19 | 202,887 | 191,104 | 11,783 | 6,845 | 10,494 | 0 | 16.7k |
| 12000 | 3/3 | 19 | 155,167 | 138,624 | 16,543 | 6,332 | 8,167 | 1 | 11.2k |
| 7000 | 3/3 | 25 | 156,138 | 128,555 | 27,583 | 8,600 | 6,246 | 4 | 7.0k |

### Per run

| compact-at | run | success | turns | input | cached input | output | peak context | compactions | seconds | load_skill / load_tools |
|---|---|---|---|---|---|---|---|---|---|---|
| off | 1 | yes | 16 | 158,999 | 147,968 | 5,984 | 15,310 | 0 | 40 | 2 / 1 |
| off | 2 | yes | 24 | 269,172 | 256,640 | 8,606 | 18,819 | 0 | 84 | 3 / 3 |
| off | 3 | yes | 18 | 180,491 | 168,704 | 5,946 | 15,838 | 0 | 40 | 2 / 1 |
| 12000 | 1 | yes | 18 | 147,702 | 130,048 | 5,888 | 10,914 | 1 | 41 | 2 / 3 |
| 12000 | 2 | yes | 22 | 194,856 | 177,024 | 6,334 | 11,919 | 1 | 46 | 3 / 5 |
| 12000 | 3 | yes | 17 | 122,943 | 108,800 | 6,774 | 10,839 | 1 | 42 | 2 / 1 |
| 7000 | 1 | yes | 24 | 149,640 | 123,392 | 7,994 | 6,978 | 4 | 58 | 2 / 5 |
| 7000 | 2 | yes | 25 | 157,742 | 130,304 | 8,793 | 6,958 | 4 | 60 | 4 / 6 |
| 7000 | 3 | yes | 26 | 161,031 | 131,968 | 9,012 | 6,993 | 4 | 61 | 4 / 6 |

### Observations

- **Success is unaffected:** 9/9 runs succeeded, including the incident whose issue the agent had to create.
- **Total input fell about 24% at both thresholds** (203k → 155–156k), so on this task compaction pays for its summary calls.
- **12,000 (one compaction) is the better setting:**
  - It takes as many turns as off, and output is 7% lower.
  - Uncached input rises 40% (11.8k → 16.5k): one planned miss after the compaction, plus the uncached part of a single summary call.
  - The summary call is about 12.5k input (94% cached) and about 700 output tokens.
- **7,000 (four compactions) saves no more input and costs more elsewhere:**
  - 6 more turns per run, mostly re-loading skills and tool schemas (`load_tools` 1.7 → 5.7 per run).
  - 26% more output (summaries are about 3k output tokens per run).
  - 2.3× the uncached input.
  - Runs take about 50% longer in wall-clock time.
- **Re-loading after compaction works, with one wrinkle:** in one 12000 run, the agent called `metrics_ack_alert` after compaction without loading its schema again. It got the argument name wrong 3 times and recovered each time from the schema in the validation error.
- **Caveat:** N=3, and the off runs vary from 159k to 269k input on their own (one off run took 24 turns). The 24% saving is the same order as that spread, so treat it as indicative. The direction matches the research: compact rarely, well below the peak but not repeatedly.

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

## Prompt cache (`TASK.md` question 1)

Prefix caches (vLLM, SGLang, llama.cpp, and hosted APIs) reuse a request's KV cache only up to the first token that differs from an earlier request. The harness therefore treats the request as `[tools][system][task][checkpoint][append-only turns]` and changes it only from the right:

- **Dynamic loading:** `tools` and the system prompt are built once per session and never change. Skill bodies and tool schemas arrive as tool results appended to the history, so loading something never edits the prefix.
- **Assistant messages** are stored exactly as received, so the history re-renders byte-identically on the next request.
- **Compaction is rare and large:** it fires at a threshold rather than trimming on every step, so each compaction is one planned miss, on a short post-compaction context. The tools, system prompt and task in front of the checkpoint stay byte-identical and stay cached (about 1.3k cached tokens on the first post-compaction turn in every run). The checkpoint is never edited until the next compaction.
- **The summary call itself hits the cache:** it sends the current history unchanged with the same `tools` and parameters, plus one appended instruction (88% cached here). A fresh summarization prompt that re-serializes the history would be a full miss.
- **Output capping happens at ingest:** large bash output is cut to head + tail before it enters the history, so it never has to be rewritten later.
