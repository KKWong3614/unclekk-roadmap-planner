# UncleKK Roadmap Planner（任务规划编排器）

> 本文为 **skillhub 版（中文优先）**。GitHub 仓库 README 请用**英文优先**版（章节顺序互换）。
> 版本 Version：**2.1.0** · 许可 License：MIT · 纯本地、零依赖、硬代码兜底。

## 这是什么（What is it）

把"大而模糊"的任务，先拆成**带依赖、带成功标准**的清单（Roadmap），再一步步执行；每步的进度、执行者、工具、时间都自动记录，可审计、可暂停、可恢复。

一句话记忆：**它是"班长"——排班、点名、传话、记日志；真正干活的是调用它的 Agent（工人）。** 它不调用大模型、不真的并行、不动态装工具。

## 30 秒上手（小白必读 Quick Start）

下面 6 行命令复制即可跑（目标是"写一篇关于本地大模型的短文"，拆成 3 步）：

```bash
# ① 建模板（complex 模式含依赖）
python scripts/planner.py new --goal "写一篇关于本地大模型的短文" --mode complex --out mini.json
# ② 用编辑器把 subtasks 改成 3 步（示例见下方），然后校验
python scripts/planner.py validate mini.json
# ③ 取第 1 步去执行
python scripts/planner.py step mini.json          # 预期：READY #1 列提纲
# ④ 标记完成（把产出写进 --output）
python scripts/planner.py complete mini.json --id 1 --output "提纲：背景/定义/3个场景/小结"
# ⑤ 继续：#2 依赖 #1，自动拿到 #1 的产出作为上下文
python scripts/planner.py step mini.json          # 预期：READY #2 写正文（带 #1 产出）
python scripts/planner.py complete mini.json --id 2 --output "正文..."
python scripts/planner.py complete mini.json --id 3 --output "小结..."
python scripts/planner.py step mini.json          # 预期：ALL DONE ✓
python scripts/planner.py summary mini.json       # 看完整记录与产出
```

3 步 `mini.json` 示例（替换 ① 生成的默认单步即可）：

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

> 小白提醒：先 `validate` 再 `step`；每步完成前对照 `success_criteria` 自检；拿不准就别 `complete`，先重做这一步。

## 谁该用（Audience · 新手 → 专业）

| 用户类型 | 怎么用 |
|---|---|
| **新手 Agent 用户** | 拿到"写报告/做调研/搭流程"这类模糊大任务，直接 `new`+`validate` 建清单，照 `step`/`complete` 一步步跑，别闷头死磕。 |
| **进阶用户** | 用 `condition` 做条件跳过、`parallel_group` 标并行、`assign` 派给不同 Worker。 |
| **专业用户** | 把清单存成可复用模板；用 `reset --force` 救回被跳过的任务；用 `summary`/`trace` 审计复盘。 |

**所有 Agent 用户通用纪律**：先规划后执行；单文件、单 Agent 顺序调用；完成前对照 `success_criteria` 自检。

## 什么时候自动用（Auto-Trigger）

满足**任一**即自动调用（不用你显式说"用 planner"）：

- **规模阈值**：子任务 **≥ 3 步且存在依赖或并行**（不是一步能搞定的小活）。
- **协作/跨域**：需 **≥ 2 个 Agent 或 ≥ 2 个文件/系统** 接力。
- **可追溯诉求**：你要求"可审计、可暂停、可恢复、可复盘"。
- **防跑偏**：担心方向跑偏，或做一半才发现漏了关键步骤。
- **可复用**：这次拆法以后可能复用（存成模板）。

不满足（如"一句话问答""单步脚本"）就**不要**触发——直接做。

## 硬保障 & 步数限制（Hard-coded Safeguards）

以下保障**写在 `scripts/planner.py` 里**，不是口号：

1. **路径遍历拒绝**：拒绝 `..`，防越权写文件。
2. **condition 沙箱**：关闭 `__builtins__`，只开放白名单变量/函数，禁文件/网络。
3. **原子写**：先写临时文件再 `os.replace`，崩溃也不留半截 JSON。
4. **重试上限 `MAX_ATTEMPTS=5`**：单任务重试达上限不再派发，防死循环。
5. **规模上限 `MAX_SUBTASKS=1000`**：`validate` 拒绝异常超大文件。
6. **级联失败**：依赖 `failed` → 下游级联 `failed`，保证严格闭环、不死锁。
7. **强制恢复 `forced`**：`reset --force` 绕过 condition 重跑被跳过任务。
8. **统一错误类型**：`PlannerError` 替代裸报错，所有异常可读。

## 被跳过的任务怎么救（Skip Recovery · 坑点）

被 `condition` 跳过的任务，**只 `reset`（不带 `--force`）没用**——下次 `step` 条件仍为假会再次跳过。
必须用 `reset --id N --force` 才会忽略条件强制重跑：

```
reset --id 8            → 仍 skipped（坑！）
reset --id 8 --force    → 可重新 step 并执行（正确）
```

## 审计报告样例（Audit Report Sample）

`summary` 直接产出可审计证据，形如：

```
目标: 写一篇关于本地大模型的短文   模式: complex   进度: 3/3
 [✓] #1 列提纲   产出: 提纲：背景/定义/3个场景/小结
 [✓] #2 写正文   产出: 正文...
 [✓] #3 写小结   产出: 小结...
执行 trace:
  2026-09-02T07:00:01+00:00 | step #1 running
  2026-09-02T07:00:05+00:00 | complete #1 done
```

完整审计报告样例见 `references/audit-report-20260713.md`、`references/test-report-20260723.md`、`references/fix-verify-20260713.md`。

## 文档导航（Docs · 无断链）

- `SKILL.md` —— 完整规范、命令速查、FAQ、硬保障、理论附录（必读）。
- `references/roadmap_schema.md` —— 字段、校验规则、condition/并行组语义。
- `references/audit-report-20260713.md` 等 —— 历史审计报告样例。
- `scripts/planner.py` / `scripts/test_planner.py` —— 实现与自测（`python scripts/test_planner.py`）。
- `CHANGELOG.md` —— 版本历史。
- `README.github.md` —— GitHub 英文优先版（本文件为 skillhub 中文优先版）。

## 版本（Version）

当前 **2.1.0**。详见 `CHANGELOG.md`。
