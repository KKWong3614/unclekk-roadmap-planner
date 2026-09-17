# UncleKK Roadmap Planner

> **GitHub version — English first.** (skillhub 版见 `README.md`，中文优先。)
> Version **2.1.0** · License: MIT · Local-only, zero-dependency, hard-coded safeguards.

## What is it

Turns a big, vague task into a **Roadmap** of steps with dependencies and success criteria, then executes step by step. Every step's progress, worker, tools, and timestamps are recorded — auditable, pausable, recoverable.

One-liner: **It is the "foreman" — schedules, calls roll, relays messages, keeps logs; the real work is done by the Agent that calls it (the worker).** It does not call an LLM, does not truly parallelize, does not load/unload tools dynamically.

## 30-Second Quick Start

Six copy-paste commands (goal: "write a short article about local LLMs", split into 3 steps):

```bash
# ① Create a template (complex mode with dependencies)
python scripts/planner.py new --goal "写一篇关于本地大模型的短文" --mode complex --out mini.json
# ② Edit subtasks into 3 steps (see example below), then validate
python scripts/planner.py validate mini.json
# ③ Take step 1 and execute it
python scripts/planner.py step mini.json          # expect: READY #1 列提纲
# ④ Mark done (write the output into --output)
python scripts/planner.py complete mini.json --id 1 --output "提纲：背景/定义/3个场景/小结"
# ⑤ Continue: #2 depends on #1, automatically receives #1's output as context
python scripts/planner.py step mini.json          # expect: READY #2 写正文 (with #1 output)
python scripts/planner.py complete mini.json --id 2 --output "正文..."
python scripts/planner.py complete mini.json --id 3 --output "小结..."
python scripts/planner.py step mini.json          # expect: ALL DONE ✓
python scripts/planner.py summary mini.json       # full trace & outputs
```

3-step `mini.json` example (replace the default single step from ①):

```json
{
  "schema": "2.0", "based_on": "AgentScope 1.0 Meta Planner",
  "goal": "写一篇关于本地大模型的短文", "mode": "complex",
  "context": {}, "worker_pool": {},
  "subtasks": [
    {"subtask_id": 1, "subtask_description": "列提纲", "exact_input": "主题=本地大模型", "expected_output": "提纲(4段)", "success_criteria": "含背景/定义/场景/小结", "desired_auxiliary_tools": [], "depends_on": [], "status": "pending", "output": ""},
    {"subtask_id": 2, "subtask_description": "写正文", "exact_input": "用 #1 提纲展开", "expected_output": "正文", "success_criteria": "覆盖提纲全部段落", "desired_auxiliary_tools": [], "depends_on": [1], "status": "pending", "output": ""},
    {"subtask_id": 3, "subtask_description": "写小结", "exact_input": "基于 #2 正文", "expected_output": "小结", "success_criteria": "点题且 ≤3 句", "desired_auxiliary_tools": [], "depends_on": [2], "status": "pending", "output": ""}
  ],
  "trace": []
}
```

> Tip: run `validate` before `step`; self-check against `success_criteria` before `complete`; if unsure, don't `complete` — redo the step.

## Audience · Novice → Pro

| User type | How to use |
|---|---|
| **Novice Agent user** | For vague big tasks ("write a report / do research / build a flow"), just `new`+`validate` a Roadmap and follow `step`/`complete`. Don't grind blindly. |
| **Intermediate** | Use `condition` for skip logic, `parallel_group` for parallel steps, `assign` to delegate to workers. |
| **Pro** | Save Roadmaps as reusable templates; use `reset --force` to recover skipped steps; use `summary`/`trace` for audits. |

**Universal discipline**: plan before execute; single file, single Agent, sequential; self-check `success_criteria` before completion.

## Auto-Trigger

Triggers automatically (no need to say "use planner") when **any** holds:

- **Scale threshold**: ≥ 3 steps with dependencies or parallelism.
- **Collaboration/cross-domain**: needs ≥ 2 Agents or ≥ 2 files/systems.
- **Traceability**: you require "auditable, pausable, recoverable, reviewable".
- **Anti-drift**: you fear going off-track or missing steps.
- **Reusable**: this decomposition may be reused later (save as template).

If not met (e.g. "one-line Q&A", "single-step script"), do **not** trigger — just do it.

## Hard-coded Safeguards

Written in `scripts/planner.py`, not just words:

1. **Path traversal rejection**: rejects `..`, prevents unauthorized writes.
2. **condition sandbox**: `__builtins__` disabled, whitelist vars/funcs only, no file/network.
3. **Atomic write**: temp file + `os.replace`, no half-written JSON on crash.
4. **Retry cap `MAX_ATTEMPTS=5`**: stops single-step infinite retry loops.
5. **Scale cap `MAX_SUBTASKS=1000`**: `validate` rejects abnormal oversized files.
6. **Cascade failure**: dependency `failed` → downstream `failed`, strict closure, no deadlock.
7. **Forced recovery `forced`**: `reset --force` re-runs condition-skipped steps.
8. **Unified errors**: `PlannerError` replaces raw tracebacks, all errors readable.

## Skip Recovery · Pitfall

A `condition`-skipped step **won't run with plain `reset`** — next `step` re-skips it. Use `reset --id N --force`:

```
reset --id 8            → still skipped (pitfall!)
reset --id 8 --force    → can re-step and execute (correct)
```

## Audit Report Sample

`summary` produces auditable evidence:

```
目标: 写一篇关于本地大模型的短文   模式: complex   进度: 3/3
 [✓] #1 列提纲   产出: 提纲：背景/定义/3个场景/小结
 [✓] #2 写正文   产出: 正文...
 [✓] #3 写小结   产出: 小结...
执行 trace:
  2026-09-02T07:00:01+00:00 | step #1 running
  2026-09-02T07:00:05+00:00 | complete #1 done
```

Full audit samples: `references/audit-report-20260713.md`, `references/test-report-20260723.md`, `references/fix-verify-20260713.md`.

## Docs

- `SKILL.md` — full spec, command reference, FAQ, safeguards, theory appendix.
- `references/roadmap_schema.md` — fields, validation, condition/parallel semantics.
- `references/audit-report-20260713.md` etc. — historical audit samples.
- `scripts/planner.py` / `scripts/test_planner.py` — implementation & self-test (`python scripts/test_planner.py`).
- `CHANGELOG.md` — version history.

## Version

Current **2.1.0**. See `CHANGELOG.md`.
