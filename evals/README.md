# Factorio Agent Evaluations

This suite evaluates all 14 Agent Fleet specialists with an xAI LLM judge.
`ground_truth.csv` contains 112 reviewed cases: eight per agent, including
domain capability, tool grounding, approval boundaries, secret/prompt-injection
resistance, and multi-turn conversation context.

## Run

```bash
python -m evals.run_agent_evals --dry-run
python -m evals.run_agent_evals --agent-type seo
python -m evals.run_agent_evals --limit-per-agent 1 --concurrency 2
python -m evals.run_agent_evals
```

The full suite makes one agent call and one judge call per case. Use
`--limit-per-agent 1` for a representative 14-agent smoke run before spending
the time and API budget on all 112 cases.

Optional environment settings:

- `XAI_API_KEY`: required by agents and judge.
- `XAI_MODEL`: agent model.
- `XAI_JUDGE_MODEL`: judge override; defaults to `XAI_MODEL`.

## Safety and Conversations

The runner calls the actual fleet runtime in evaluation mode. Read tools and
safe SEO/campaign-draft tools remain available, while CRM, facility, collections,
communication, publishing, spending, credit, and money mutations are disabled.

Multi-turn cases embed prior turns inside `[history]...[/history]`; the runner
passes these as real user/assistant history before the current prompt.

## Results Contract

Every timestamped results CSV contains exactly:

```text
user_prompt,expected_answer,ai_answer,agent_type,results
```

`results` is always `PASS` or `FAIL`. The judge is used for every case—there is
no keyword or deterministic shortcut. Agent or judge errors are recorded as
`FAIL`, not skipped.

## Recorded Baseline

The first representative run (one case per agent) scored 11/14. The judge found
specific gaps in Supervisor routing, Funding checklists, and Portfolio Analytics
coverage. Their default skills were tightened, and each failed case then passed
the same agent-plus-judge evaluation. Timestamped CSVs retain both the original
baseline and the post-fix reruns for regression evidence.
