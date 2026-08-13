# Roadmap Schema（v2.0）

依据 AgentScope 1.0 Meta Planner 的架构设计落地。论文中 Meta Planner 的核心是：

> "...hierarchical task decomposition through structured roadmap generation,
> dynamic worker agent instantiation with specialized toolkit allocation,
> and persistent state management enabling long-term task continuity."
>
> "RoadmapManager... facilitates intelligent task breakdown into executable subtasks
> with defined dependencies and success criteria."
>
> "WorkerManager... allocates appropriate tool combinations—including MCP
> for external service integration—based on subtask requirements."

本 schema 把上述概念映射为可运行的 JSON 结构。

---

## 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| schema | string | 是 | 固定 `"2.0"` |
| based_on | string | 否 | 理论来源标注，便于追溯 |
| goal | string | 是 | 高层目标 |
| mode | string | 是 | `simple` 或 `complex`，见下文双模式说明 |
| context | object | 否 | 贯穿全任务的共享上下文（key-value） |
| worker_pool | object | 否 | Worker 注册表（key=worker 名，value=元信息） |
| subtasks | array | 是 | 子任务数组，至少 1 个 |
| trace | array | 否 | 执行事件日志（由 complete 自动追加） |
| created_at | string | 否 | ISO 8601 创建时间（自动写入） |
| updated_at | string | 否 | ISO 8601 更新时间（自动写入） |

## subtask 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| subtask_id | int | 是 | 唯一标识，建议从 1 递增 |
| subtask_description | string | 是 | 可执行描述，避免模糊词 |
| exact_input | string | 是 | 本步精确输入，可引用前序产出 |
| expected_output | string | 是 | 本步期望产出，需能喂给下一步 |
| success_criteria | string | 否 | 如何判断本步算完成（论文 success criteria） |
| desired_auxiliary_tools | array[string] | 否 | 本步所需工具，越精简越好（论文 specialized toolkit allocation） |
| depends_on | array[int] | 否 | 依赖的子任务 id；构成 DAG（论文 defined dependencies） |
| parallel_group | string | 否 | 并行组名；同组任务会被一起返回执行 |
| condition | string | 否 | Python 条件表达式；false 时本步被 skipped |
| assigned_worker | string | 否 | 已分配给哪个 Worker（论文 dynamic worker instantiation） |
| status | string | 否 | `pending` / `running` / `done` / `skipped` / `failed`（注：`ready` 为调度器内部态，不写入文件；运行时子任务只处于上述五态之一） |
| output | string | 否 | 执行完写入的实际产出，传给下游 |
| started_at | string | 否 | 开始执行时间 |
| completed_at | string | 否 | 完成/跳过时间 |
| attempts | int | 否 | 尝试次数（step 时自动 +1） |

---

## 双模式说明

### mode = simple

对应论文"lightweight ReAct processing for simple tasks"。

- `subtasks` 必须且只能有 1 个。
- 不允许 `depends_on`。
- `step` 直接返回该子任务，`complete` 后直接 `ALL DONE`。

### mode = complex

对应论文"comprehensive planning-execution patterns for complex multi-stage problems"。

- `subtasks` 可以有多个，通过 `depends_on` 构成 DAG。
- 支持 `parallel_group`、`condition`、`assigned_worker`。
- `step` 按 DAG 拓扑返回当前可执行的子任务（单个或同组多个）。

---

## 校验规则（planner.py validate）

1. root 必须是 JSON 对象，含 `goal`。
2. `subtasks` 必须是非空数组。
3. 每个 subtask 必须有 `subtask_id` / `subtask_description` / `exact_input` / `expected_output`。
4. `subtask_id` 不可重复。
5. `depends_on` 中的 id 必须指向存在的子任务。
6. `depends_on` 构成的图必须无环（DAG）。
7. `mode=simple` 时：`subtasks` 长度必须为 1 且不能有依赖。
8. `parallel_group` 与 `condition` 必须为字符串或 null。

---

## 上下文传递（planner.py step）

执行子任务 `#N` 时，调度器会：

1. 收集所有 `depends_on` 中已完成（done）子任务的 `output`。
2. 按 `subtask_id` 顺序拼接成"前置上下文"文本。
3. 连同 `exact_input` / `expected_output` / `success_criteria` / `desired_auxiliary_tools` / `assigned_worker` 一并输出给调用 Agent。

若依赖项被 `condition` 判定为 skipped（无产出），则该依赖视为已满足，但不进入上下文。

---

## 条件表达式（condition）

`condition` 是一个 Python 表达式字符串，在沙箱内求值：

- 可用变量：`outputs`（dict[int, str]，已完成子任务产出）、`goal`（str）、`context`（dict）。
- 可用函数：`len`, `bool`, `str`, `int`, `float`, `any`, `all`。
- 不可用 `__builtins__`，不可进行文件/网络等副作用操作。
- 返回 truthy 则执行本任务；返回 falsy 则本任务被标记为 `skipped`。

示例：

```json
"condition": "len(outputs.get(5, \"\")) > 50"
```

---

## 并行组（parallel_group）

- 同组的子任务必须拥有相同的 `parallel_group` 字符串。
- 调度器只有在整组所有**尚未完成**的成员都满足依赖时，才会把这组任务一起返回。
- 是否真并行执行由调用 Agent 决定；本技能只负责"一起放出"。

---

## 完整示例

```json
{
  "schema": "2.0",
  "based_on": "AgentScope 1.0 Meta Planner",
  "goal": "撰写竞品报告",
  "mode": "complex",
  "context": {"market": "AI 竞品分析工具"},
  "worker_pool": {},
  "subtasks": [
    {
      "subtask_id": 1,
      "subtask_description": "锁定核心竞品",
      "exact_input": "目标市场=context.market",
      "expected_output": "竞品清单",
      "success_criteria": "不少于 3 个竞品",
      "desired_auxiliary_tools": ["search"],
      "depends_on": [],
      "status": "pending",
      "output": ""
    },
    {
      "subtask_id": 2,
      "subtask_description": "收集竞品公开信息",
      "exact_input": "使用 #1 的竞品清单",
      "expected_output": "每个竞品的信息卡片",
      "desired_auxiliary_tools": ["search", "browser"],
      "depends_on": [1],
      "parallel_group": "collect",
      "status": "pending",
      "output": ""
    },
    {
      "subtask_id": 3,
      "subtask_description": "收集市场宏观数据",
      "exact_input": "搜索市场规模、趋势、用户画像",
      "expected_output": "宏观数据摘要",
      "desired_auxiliary_tools": ["search"],
      "depends_on": [1],
      "parallel_group": "collect",
      "status": "pending",
      "output": ""
    },
    {
      "subtask_id": 4,
      "subtask_description": "拆解对比维度",
      "exact_input": "综合 #2 和 #3 的产出",
      "expected_output": "对比维度表",
      "depends_on": [2, 3],
      "status": "pending",
      "output": ""
    }
  ],
  "trace": []
}
```
