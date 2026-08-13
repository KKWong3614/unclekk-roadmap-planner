---
name: unclekk-roadmap-planner
slug: unclekk-roadmap-planner
displayName: unclekk Roadmap Planner
version: 2.0.1
summary: 依据论文 Meta Planner 模块实现的"先规划、再执行"编排器：DAG 依赖调度、并行组、条件跳过、Worker 分配、可审计可恢复。
description: '依据 AgentScope 1.0 论文 Meta Planner 模块设计的"先规划、再执行"编排器。

  支持复杂任务的 DAG 依赖调度、并行组、条件跳过、Worker 分配、工具组合提示、

  持久状态与任务恢复。本技能是编排器，不直接调用 LLM；真正的 Worker 执行由调用 Agent 完成。


  解决的问题：

  - Agent 拿到复杂任务就闷头死磕、方向跑偏。

  - 多步骤任务上下文断裂、无法接力。

  - 任务执行不可见、不可调试、不可恢复。


  触发条件：复杂多步骤任务、需要先规划再执行、需要把大目标拆成可审计子任务、

  写长文/做研究/搭流程/多 Agent 协作编排。


  关键词：Meta Planner、Roadmap、任务分解、DAG、并行组、条件跳过、WorkerManager、

  工具分配、先规划后执行、可审计、可恢复。

  '
license: MIT
author: KK大叔 (UncleKK)
metadata:
  source_paper: 'AgentScope 1.0: A Developer-Centric Framework for Building Agentic Applications (arXiv:2508.16279v1), Alibaba Group'
  agent_created: true
  category: productivity
---

# unclekk-roadmap-planner

> **理论来源**：AgentScope 1.0 论文的 **Meta Planner** 模块（第 3.2 节前后）。
> 论文原文指出：Meta Planner 采用双模式架构，在简单任务时使用轻量 ReAct，
> 在复杂多阶段任务时使用 planning-execution pipeline；核心包含三大功能模块：
> 1) 结构化 Roadmap 生成（把任务拆为带依赖与成功标准的子任务）；
> 2) Worker 分配记录 + 专用工具集分配（本技能记名，实际实例化由 Agent 完成）；
> 3) 持久状态管理以支持任务续跑与调试。
>
> 本技能是上述思想的**轻量、可运行、零第三方依赖**的实现，
> 重点落在 **RoadmapManager** 的调度语义与 **WorkerManager** 的 Worker/工具分配记录上。

---

## 重要说明：哪些是代码真实现的，哪些交给调用 Agent

这是为了**不再夸大**而必须说清楚的分工边界：

| 能力 | 本技能是否实现 | 说明 |
|---|---|---|
| Roadmap 数据结构、校验、持久化 | ✅ 代码实现 | JSON schema、DAG 无环检测、依赖解析 |
| 双模式（simple/complex） | ✅ 代码实现 | simple 模式强制单步无依赖；complex 模式启用完整调度 |
| DAG 依赖调度 | ✅ 代码实现 | 按 `depends_on` 拓扑排序，skipped 也视为依赖满足 |
| 并行组 fan-out/fan-in | ✅ 代码实现 | 同 `parallel_group` 的任务一起返回 |
| 条件跳过 | ✅ 代码实现 | `condition` 表达式求值，false 则标记 skipped |
| Worker 分配 | ✅ 代码实现 | `assign` 命令与 `assigned_worker` 字段 |
| 工具组合提示 | ✅ 代码实现 | `desired_auxiliary_tools` 字段并随 step 输出 |
| 任务恢复/重置 | ✅ 代码实现 | `reset` 命令 |
| 原子写 + 错误处理 | ✅ 代码实现 | 临时文件 + os.replace；非法 JSON/缺文件给出可读错误 |
| 实际的 LLM 调用 / Worker 执行 | ❌ 交给调用 Agent | 本技能只告诉 Agent"下一步做什么、带什么上下文、用什么工具" |
| 真正的并行执行 | ❌ 交给调用 Agent | 本技能把同组任务一起返回；是否真并行由 Agent 决定 |
| 动态加载/卸载 MCP 工具 | ❌ 交给调用 Agent | 本技能只提示工具名，实际装配由 Agent 的工具层完成 |

**一句话**：本技能是"班长"，负责排班、点名、传话、记日志；Agent 是"工人"，真正干活。

---

## 什么时候用

- 用户给了一个**模糊但复杂**的目标（"帮我写一份竞品报告""调研一下 XX 能不能用"）。
- 任务明显需要**多步骤、有先后依赖或可以并行**。
- 你怕**方向跑偏**或**做到一半才发现漏了关键步骤**。
- 这次任务的拆解方式**以后可能复用**。
- 需要**可审计、可暂停、可恢复**的执行记录。

只要命中以上任一，先调用本技能建 Roadmap，再执行。

---

## 核心思想（一句话）

**先拆成 Roadmap，再按 DAG 调度执行；依赖任务的产出自动传给下游；每一步的状态、Worker、工具、时间戳都留痕。**

---

## 命令总览

脚本位置：`scripts/planner.py`，任意 Python 环境可直接运行。

```bash
# 1. 新建 roadmap 模板
python scripts/planner.py new --goal "撰写竞品报告" --mode complex --out roadmap.json

# 2. （Agent 用 LLM 把 subtasks 拆满，然后校验）
python scripts/planner.py validate roadmap.json

# 3. 分配 Worker（可选，WorkerManager 语义）
python scripts/planner.py assign roadmap.json --id 2 --worker "researcher-1"

# 4. 逐个/逐组执行
python scripts/planner.py step roadmap.json [--worker "researcher-1"]
#   → Agent 执行返回的子任务
python scripts/planner.py complete roadmap.json --id 1 --output "执行结果..."
#   → 重复 step / complete 直到 ALL DONE

# 5. 查看状态与完整 trace
python scripts/planner.py status roadmap.json
python scripts/planner.py summary roadmap.json

# 6. 任务恢复/调试
python scripts/planner.py reset roadmap.json          # 全部重置
python scripts/planner.py reset roadmap.json --id 3   # 只重置 #3

# 7. 生成示例 roadmap
python scripts/planner.py demo --out demo_roadmap.json
```

🔴 CHECKPOINT · 执行前必须确认
- 每跑一次 `step` 后，先读它返回的**前置上下文**与 `desired_auxiliary_tools`，确认够用再动手。
- 每跑一次 `complete` 前，对照该子任务的 `success_criteria` 自检产出是否达标；不达标就别 complete，先重做这一步。
- `reset` 会清空进度，执行前确认你真的要从某步（或全部）重来。

---

## 故障处理与失败模式（必读）

每条都是"命令报错/异常 → 你该怎么做"的明确分支，照着处理即可：

| 现象 | 触发原因 | 一线修复 | 仍不行兜底 |
|---|---|---|---|
| `validate` 退出码 1，列出若干错误 | roadmap 不满足 schema（缺必填 / 重复 id / 有环 / 依赖指向不存在） | 按报错逐条改对应字段；重复 id 改唯一；有环就去掉某个 `depends_on`；依赖 id 改成存在的 | 跑 `python scripts/planner.py new --mode complex` 重新生成干净模板再填 |
| `step` 报"依赖尚未完成或条件未满足"并退出 1 | 有 pending 子任务的依赖没 done/skipped | 先 `complete` 它的上游依赖；或确认上游 `condition` 是否把它 skip 了 | 用 `status` 看全局，定位卡在哪个上游 |
| `complete --id N` 报"依赖 #M 尚未完成" | 你跳步了，没先完成上游 | 先 `complete #M`（及其上游链） | 若 #M 本应被 skip，检查它的 `condition` 是否写错 |
| `step`/`complete` 报 JSON 解析错误 | roadmap.json 被截断 / 手改坏 | 从备份或 `demo` 重新生成；用 `status` 看是否已部分损坏 | 用 `reset` 清空重来（见上） |
| `condition` 求值报错（表达式非法 / 用了禁函数） | `condition` 字符串写了不在白名单的标识符或语法错 | 改成只用 `outputs`/`goal`/`context` + `len`/`bool`/`str`/`int`/`float`/`any`/`all` | 直接把 `condition` 设为 `null` 强制走执行分支 |
| `step` 返回 `WAITING` | 上一步被标 `running` 但还没 `complete` | 去 `complete` 那个 running 的任务 | 若卡死，用 `reset --id N` 把它退回 pending 重跑 |

---

## Roadmap 核心字段

完整字段与校验规则见 `references/roadmap_schema.md`。这里只列灵魂字段：

```json
{
  "schema": "2.0",
  "based_on": "AgentScope 1.0 Meta Planner",
  "goal": "高层目标",
  "mode": "simple | complex",
  "context": {},
  "worker_pool": {},
  "subtasks": [
    {
      "subtask_id": 1,
      "subtask_description": "这一步要做什么",
      "exact_input": "这一步的精确输入（可引用上一步产出）",
      "expected_output": "这一步期望产出的东西",
      "success_criteria": "如何判断这一步算完成",
      "desired_auxiliary_tools": ["search", "browser"],
      "depends_on": [],
      "parallel_group": "collect",
      "condition": null,
      "assigned_worker": "researcher-1",
      "status": "pending",
      "output": ""
    }
  ]
}
```

**拆解要点**（完整字段与校验规则见 `references/roadmap_schema.md`）：
- `subtask_description` 必须**可执行**，不是"研究一下"这种模糊词。
- `exact_input`/`expected_output` 要能咬合——上一步的产出就是下一步的输入。
- `depends_on` 构成 DAG，调度按依赖拓扑而非 id 顺序。
- `success_criteria` 用于 Agent 自检产出是否达标。
- `desired_auxiliary_tools` 越精简越好，避免 Agent 选择困难、上下文污染。

---

## 示例：竞品报告 Roadmap（demo）

运行 `python scripts/planner.py demo --out demo_roadmap.json` 会生成一份包含以下设计的示例：

- `#2 收集竞品公开信息` 与 `#3 收集市场宏观数据` 同处 `parallel_group: collect`，
  在 `#1` 完成后会**一起返回**，供 Agent 并行执行。
- `#8 补充数据可视化` 带 `condition: len(outputs.get(5, "")) > 50`，
  只有当 `#5` 的产出足够长时才会执行，否则自动 skipped。
- `#9 复核与定稿` 依赖 `#7` 与 `#8`；若 `#8` 被跳过，`#9` 仍可继续执行。

这份 demo 可以直接作为"竞品报告生产流程"的可复用模板。

---

## 自测

```bash
python scripts/test_planner.py
```

覆盖：simple 模式、校验错误、DAG+并行组、条件跳过、乱序完成拦截、Worker 分配。

### 文件说明
- `results.tsv`、`test-prompts.json`：进化/回归测试痕迹，非运行必需，仅供审计与人工验收参考。

---

## 生产力收益

- **方向可见**：动手前就把计划摆出来，用户/你自己能先纠偏。
- **上下文不断裂**：按 `depends_on` 聚合前置产出，Agent 不会"忘掉前面做了啥"。
- **可审计**：每一步有输入/产出/状态/时间戳/Worker，出错能定位到哪一步。
- **可复用**：Roadmap 模板存下来，同类任务直接套。
- **可恢复**：`reset` 支持从任意步骤重跑，适合长任务中断续跑。
- **不夸大**：文档里明确写了哪些是代码实现、哪些交给 Agent，避免"货不对板"。

---

## 注意事项

- 本技能**不调用 LLM**，真正执行子任务的是调用 Agent（或它调度的工具）。
- `condition` 表达式在安全沙箱内求值（无 `__builtins__`，仅开放 `outputs/goal/context` 及少量函数），不能写文件/网络请求等副作用代码。
- `desired_auxiliary_tools` 只是**提示**：本技能把它随 step 输出，Agent 据此决定加载哪些工具。
- 并发修改同一 `roadmap.json` 仍可能冲突；本技能采用原子写降低风险，但未实现跨进程文件锁。**约束：同一 roadmap 文件必须由单一 Agent 顺序调用**，禁止两个 Agent/进程同时 step/complete。

---

## 反例与黑名单（不要这样做）

- ❌ **不要绕过规划直接干活**：拿到复杂任务先 `new` + `validate` 建 Roadmap，别闷头死磕——这正是本技能要治的毛病。
- ❌ **不要在 `exact_input` / `expected_output` 写模糊词**（"研究一下""一些东西"）：下游拿不到可接力的产出，链条断裂。
- ❌ **不要给 `desired_auxiliary_tools` 塞一堆工具**：只列本步真用的，避免 Agent 选择困难、上下文污染（对应论文 specialized toolkit allocation）。
- ❌ **不要用 `depends_on` 制造环**：调度器会 `validate` 拒绝；真要循环请拆成"多次 complete 同一任务"或拆子任务。
- ❌ **不要把 `condition` 当万能开关写副作用代码**：沙箱禁 `__builtins__` 与文件/网络，只能读 `outputs`/`goal`/`context` 做判断。
- ❌ **不要并发多进程狂写同一个 roadmap.json**：本技能只做原子写、无跨进程锁，抢写会丢更新；串行或单进程操作。
- ❌ **不要夸大本技能能力**：它不调 LLM、不真并行、不动态装卸 MCP；这些交给调用 Agent。文档里"实现/未实现"边界是诚实声明，对外别说成"全自动 Agent 框架"。
