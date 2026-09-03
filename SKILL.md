---
slug: unclekk-roadmap-planner
name: unclekk-roadmap-planner
displayName: UncleKK Roadmap Planner
version: 2.1.0
summary: 依据 AgentScope 1.0 Meta Planner 的"先规划、再执行"编排器。DAG 依赖调度、并行组、条件跳过、Worker 分配、可审计可恢复。纯本地、零依赖、硬代码兜底。
description: |
  依据 AgentScope 1.0 论文 Meta Planner 模块设计的"先规划、再执行"编排器（轻量、可运行、零第三方依赖）。
  支持复杂任务的 DAG 依赖调度、并行组、条件跳过、Worker 分配、工具组合提示、持久状态与任务恢复。
  本技能是编排器，不直接调用 LLM；真正的 Worker 执行由调用 Agent 完成。
  适用：所有 Agent 用户（新手→专业）面对的多步骤、可复用、需可审计的任务。

  解决的问题：
  - Agent 拿到复杂任务就闷头死磕、方向跑偏。
  - 多步骤任务上下文断裂、无法接力。
  - 任务执行不可见、不可调试、不可恢复。

  触发条件（自动）：子任务数 ≥3 且存在依赖/并行；或任务跨 ≥2 个 Agent/文件；或用户要求可审计/可追溯；或你担心方向跑偏、漏步骤。

  关键词：Meta Planner、Roadmap、任务分解、DAG、并行组、条件跳过、WorkerManager、工具分配、先规划后执行、可审计、可恢复。
license: MIT
metadata:
  version: 2.1.0
  source_paper: "AgentScope 1.0: A Developer-Centric Framework for Building Agentic Applications (arXiv:2508.16279v1), Alibaba Group"
  agent_created: true
  category: productivity
  changelog:
    - "2.1.0: 新增 reset --force 强制重跑被 condition 跳过的任务（修复 R 项'跳过无法重跑'）；running 不再被重复派发（修 attempts 无限膨胀）；依赖失败级联失败保证严格闭环；新增 MAX_ATTEMPTS/MAX_SUBTASKS 硬代码兜底。"
    - "2.0.0: 双模式、DAG 调度、并行组、条件跳过、Worker 分配、原子写、可恢复。"
---

# unclekk-roadmap-planner · 任务规划编排器 (UncleKK Roadmap Planner)

> **一句话 (One-liner)**：把复杂任务先拆成带依赖与成功标准的 Roadmap，再按 DAG 调度执行；每步的状态、Worker、工具、时间戳都留痕，可审计、可暂停、可恢复。
> 本技能是"班长"：排班、点名、传话、记日志；**真正干活的是调用 Agent（工人）**。它不调用 LLM、不真并行、不动态装卸工具。

---

## 0. 受众与适用 (Audience) · 新手 → 专业

| 用户类型 | 你该怎么用 |
|---|---|
| **新手 Agent 用户 (Novice)** | 拿到"写报告 / 做调研 / 搭流程"这类模糊大任务时，直接 `new`+`validate` 建 Roadmap，照着 `step`/`complete` 一步步跑，别闷头死磕。 |
| **进阶用户 (Intermediate)** | 用 `condition` 做条件跳过、用 `parallel_group` 标记可并行步骤、用 `assign` 把子任务派给不同 Worker。 |
| **专业用户 (Pro)** | 把 Roadmap 当可复用模板存盘；用 `reset --force` 恢复被跳过的任务；用 `summary`/`trace` 做审计与复盘。 |

**所有 Agent 用户通用纪律**：单文件、单 Agent 顺序调用；先规划后执行；完成前对照 `success_criteria` 自检。

---

## 1. 自动触发条件 (Auto-Trigger) · 何时该用它

满足**任一**即自动调用（无需用户显式说"用 planner"）：

- **规模阈值**：子任务 **≥ 3 步且存在依赖或并行**（即不是一步能搞定的线性小活）。
- **协作/跨域**：任务需 **≥ 2 个 Agent 或 ≥ 2 个文件/系统** 接力。
- **可追溯诉求**：用户要求"可审计、可暂停、可恢复、可复盘"。
- **防跑偏**：你担心方向跑偏，或做到一半才发现漏了关键步骤。
- **可复用**：这次拆解方式以后可能复用（存成模板）。

不满足（如"一句话问答""单步脚本"）则**不要**触发——直接做。

---

## 2. 5 分钟最小可运行示例 (Minimal Runnable Example)

下面是一条命令即可复现的最小流程（含预期输出）。目标是"写一篇关于 X 的短文"，拆成 3 步。

```bash
# ① 建模板（complex 模式，含依赖）
python scripts/planner.py new --goal "写一篇关于本地大模型的短文" --mode complex --out mini.json

# ② 用编辑器把 subtasks 改成 3 步（见下），然后校验
python scripts/planner.py validate mini.json

# ③ 取第一步并执行
python scripts/planner.py step mini.json
# 预期输出：
#   READY #1: 列提纲
#   --- subtask #1 ---
#   描述: 列提纲
#   ...（精确输入/期望产出/成功标准/工具组合）

# ④ 标记完成（把产出写进 --output）
python scripts/planner.py complete mini.json --id 1 --output "提纲：背景/定义/3个使用场景/小结"

# ⑤ 继续：#2 依赖 #1 → 自动拿到 #1 的产出作为前置上下文
python scripts/planner.py step mini.json
# 预期输出：
#   READY #2: 写正文
#   --- subtask #2 ---
#   前置上下文（来自依赖项产出）:
#   [#1 列提纲]
#   提纲：背景/定义/3个使用场景/小结      ← 上一步产出自动传下来

# ⑥ 完成 #2、#3，最后看总进度
python scripts/planner.py complete mini.json --id 2 --output "正文..."
python scripts/planner.py step mini.json      # → READY #3
python scripts/planner.py complete mini.json --id 3 --output "小结..."
python scripts/planner.py step mini.json      # → ALL DONE ✓
python scripts/planner.py summary mini.json   # 看完整 trace 与产出
```

**3 步的 mini.json 示例**（替换 ① 生成的默认单步即可）：
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

---

## 3. 能力边界 (Capability Boundary) · 它做什么 / 不做什么

| 能力 | 本技能是否实现 | 说明 |
|---|---|---|
| Roadmap 结构、校验、持久化 | ✅ 代码实现 | JSON schema、DAG 无环检测、依赖解析 |
| 双模式（simple / complex） | ✅ 代码实现 | simple 强制单步无依赖；complex 启用完整调度 |
| DAG 依赖调度 | ✅ 代码实现 | 按 `depends_on` 拓扑；skipped 也视为依赖满足 |
| 并行组 fan-out/fan-in | ✅ 代码实现 | 同 `parallel_group` 的任务一起返回 |
| 条件跳过 (condition) | ✅ 代码实现 | 表达式求值，false → skipped |
| Worker 分配 / 工具组合提示 | ✅ 代码实现 | `assign` 命令 + `desired_auxiliary_tools` 随 step 输出 |
| 任务恢复 / 重置 | ✅ 代码实现 | `reset`；v2.1 新增 `reset --force` 强制重跑被跳过的任务 |
| 原子写 + 错误处理 + 路径防护 | ✅ 代码实现 | 临时文件 + `os.replace`；拒绝 `..` 遍历 |
| 重试上限 / 规模上限兜底 | ✅ 代码实现（v2.1） | `MAX_ATTEMPTS=5`、`MAX_SUBTASKS=1000` |
| 依赖失败级联失败 | ✅ 代码实现（v2.1） | 依赖 failed → 下游级联 failed，保证闭环 |
| 实际的 LLM 调用 / Worker 执行 | ❌ 交给调用 Agent | 本技能只告诉 Agent"下一步做什么、带什么上下文、用什么工具" |
| 真正的并行执行 | ❌ 交给调用 Agent | 本技能把同组任务一起返回；是否真并行由 Agent 决定 |
| 动态加载/卸载 MCP 工具 | ❌ 交给调用 Agent | 本技能只提示工具名，实际装配由 Agent 工具层完成 |

> 不夸大：文档明确写了"代码实现 / 交给 Agent"的边界，对外别说成"全自动 Agent 框架"。

---

## 4. 命令速查 (Commands)

```bash
python scripts/planner.py new --goal "目标" --mode complex --out roadmap.json   # 建模板
python scripts/planner.py validate roadmap.json                                # 校验（step/complete 前必跑）
python scripts/planner.py assign roadmap.json --id 2 --worker "researcher-1"   # 分配 Worker
python scripts/planner.py step roadmap.json [--worker "researcher-1"]          # 取下一步/组 + 前置上下文
python scripts/planner.py complete roadmap.json --id 1 --output "产出..."      # 标记完成/跳过/失败
python scripts/planner.py status roadmap.json                                  # 当前进度
python scripts/planner.py summary roadmap.json                                 # 完整 trace 与产出
python scripts/planner.py reset roadmap.json [--id 3] [--force]                # 重置（--force 强制重跑被跳过的任务）
python scripts/planner.py demo --out demo_roadmap.json                         # 生成竞品报告示例
```

🔴 **执行前 CHECKPOINT：**
- 每跑 `step` 后，先读返回的**前置上下文**与 `desired_auxiliary_tools`，确认够用再动手。
- 每跑 `complete` 前，对照该子任务 `success_criteria` 自检产出是否达标；不达标就别 complete，先重做这一步。
- `reset` 会清空进度，执行前确认你真的要从某步（或全部）重来。

---

## 5. 常见问题 FAQ · 简短 + 实例 + 坑点

**Q1：被 `condition` 跳过的任务，之后还能跑吗？**
能，用 `reset --id N --force`。
> **坑点 (Pitfall)**：只 `reset`（不带 `--force`）没用——下次 `step` 条件仍为假会再次跳过。必须用 `--force` 才会忽略条件强制重跑。
> **对照 (Before→After)**：`reset --id 8` → 仍 skipped；`reset --id 8 --force` → 可重新 `step` 并执行。

**Q2：任务卡住、step 报"没有可执行的子任务"怎么办？**
先看 `status`：若有 `failed` 任务，它的下游会被**级联标记 failed**。用 `reset --id N` 把失败任务退回 pending 再重试；或 `reset` 全部。

**Q3：一个任务反复失败、attempts 一直涨？**
单任务重试上限 `MAX_ATTEMPTS=5`。达到上限后不再派发，提示你 `reset --id N` 后重试（reset 会清零 attempts）。这是防死循环的硬兜底，不是 bug。

**Q4：`condition` 怎么写才安全？**
沙箱内求值，禁用 `__builtins__`，只能用 `outputs`/`goal`/`context` + `len/bool/str/int/float/any/all`。不能写文件/网络。
> **坑点**：别写 `import`、别调 `open()`——会直接报错并阻断 step。

**Q5：能并行吗？**
`parallel_group` 相同的任务会被 `step` **一起返回**，但是否真并行由你（Agent）决定；本技能只负责"一起放出"。

**Q6：和直接让 Agent 干活比，有什么用？**
方向可见（动手前先纠偏）、上下文不断裂（按依赖自动传产出）、可审计（每步留痕）、可复用（模板存盘）、可恢复（reset 续跑）。

**Q7：不要这样做（反模式）：**
- ❌ 绕过规划直接闷头干（这正是本技能要治的毛病）。
- ❌ `exact_input`/`expected_output` 写模糊词（"研究一下"）→ 下游拿不到可接力产出。
- ❌ `desired_auxiliary_tools` 塞一堆工具 → Agent 选择困难、上下文污染。
- ❌ 用 `depends_on` 制造环 → `validate` 直接拒绝。
- ❌ 两个 Agent/进程同时狂写同一个 `roadmap.json` → 串行或单进程操作。

---

## 6. 审计报告样例 (Audit Report Sample)

本技能自带完整 trace，可直接产出审计证据。运行 `summary` 得到类似：

```
目标: 写一篇关于本地大模型的短文
模式: complex
进度: 3/3
----------------------------------------
 [✓] #1 列提纲
     产出: 提纲：背景/定义/3个使用场景/小结
 [✓] #2 写正文
     产出: 正文...
 [✓] #3 写小结
     产出: 小结...
----------------------------------------
执行 trace:
  2026-09-02T07:00:01+00:00 | step #1 running
  2026-09-02T07:00:05+00:00 | complete #1 done
  2026-09-02T07:00:06+00:00 | step #2 running
  ...
```

**安全自审计（安装/升级后必跑）**：扫描是否有破坏性模式（呼应漂移自查告警）：
```bash
grep -rnE "rm -rf|rm -fr|format |dd if=|curl .*\| ?bash|wget .*\| ?bash" \
  "$HOME/.workbuddy/skills/unclekk-roadmap-planner"
```
> 历史审计报告参考：`references/audit-report-20260713.md`、`references/test-report-20260723.md`、`references/fix-verify-20260713.md`。

---

## 7. 硬代码保障 (Hard-coded Safeguards) · 不只是声明

以下保障**写在 `scripts/planner.py` 里**，不是文档口号：

1. **路径遍历拒绝**：`_sanitize_path` 拒绝显式 `..`，防越权写文件。
2. **condition 沙箱**：`safe_eval_condition` 关闭 `__builtins__`，仅开放白名单变量/函数，禁文件/网络副作用。
3. **原子写**：先写临时文件再 `os.replace`，崩溃也不留半截 JSON。
4. **重试上限 `MAX_ATTEMPTS=5`**：防单任务死循环。
5. **规模上限 `MAX_SUBTASKS=1000`**：`validate` 拒绝异常超大文件。
6. **级联失败**：依赖 `failed` → 下游级联 `failed`，保证严格闭环、不死锁。
7. **强制恢复 `forced`**：`reset --force` 绕过 condition 重跑被跳过任务（见 FAQ Q1）。
8. **统一错误类型**：`PlannerError` 替代裸 traceback，所有异常可读。

---

## 8. 更新日志 (Changelog)

- **2.1.0**（本次改进，响应 TRACE 测评）
  - 新增 `reset --id N --force`：修复"被 condition 跳过的任务无法重新执行"（R 项 4.5 核心短板）。
  - `ready_subtasks` 不再把 `running` 态任务重复派发，修掉 `attempts` 无限膨胀隐患。
  - 依赖失败**级联失败**，保证严格闭环（"兜底保障"）。
  - 新增 `MAX_ATTEMPTS` / `MAX_SUBTASKS` 硬代码兜底（"步数限制"）。
  - 文档对齐 9 点：双语标题、受众分层、最小可运行示例、自动触发阈值、FAQ 坑点、审计报告样例、硬代码保障清单。
- **2.0.0**：双模式、DAG 调度、并行组、条件跳过、Worker 分配、原子写、可恢复。

---

## 附录 A. 理论来源 (Theory, 选读)

依据 **AgentScope 1.0** 论文的 **Meta Planner** 模块（双模式：简单任务用轻量 ReAct，复杂多阶段任务用 planning-execution pipeline）。核心三模块：结构化 Roadmap 生成、Worker 分配 + 专用工具集分配、持久状态管理以支持续跑与调试。本技能是其**轻量、可运行、零依赖**的实现，重点落在 `RoadmapManager` 调度语义与 `WorkerManager` 的分配记录上。

## 附录 B. 字段与 Schema

完整字段、校验规则、condition/并行组语义见 **`references/roadmap_schema.md`**（必读，无断链）。
相对路径（相对本技能目录）：`scripts/planner.py`、`scripts/test_planner.py`、`references/roadmap_schema.md`。
自测：`python scripts/test_planner.py`（覆盖 simple / 校验错误 / DAG+并行 / 条件跳过 / 乱序拦截 / Worker 分配 / 失败恢复 / **跳过强制恢复**）。
