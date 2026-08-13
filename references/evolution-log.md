# unclekk-roadmap-planner 进化日志

> 方法论：darwin-skill（9维rubric + 棘轮 + 独立评估 + 运行时中立）+ skill-evolver（策略多样性 + 对比式补丁 + 独立审计9条 + 探索性重写）
> 非 git 仓库：用文件备份代替 `git revert`（历史备份目录：`agentscope-meta-planner_v2_preopt` / `agentscope-meta-planner_v1_backup`，已随更名归档，不在当前包内）

## 基线（2026-07-12）

- 评分：78.7 / 100（独立 agent 实跑 + 9维结构评分）
- 最弱维度：dim4 检查点(4/6)、dim9 反例黑名单(4/6)、dim3 失败模式编码(6/12)
- skill-evolver 审计：7/9 PASS，2 NEEDS_REVISION（#5 LLM填充步骤隐含、#8 "忠实实现"不可追溯断言）
- 代码瑕疵：独立审计发现 `cmd_step` 仅在 ready 非空时 save，纯 skip 分支的 skipped 状态不落盘

## 轮次 1 — 2026-07-12（applied, 78.7 → 96.0）

### 策略变体（证据来源）
- 基线独立 agent 的评分卡 + 审计问题清单，定位 dim3/dim4/dim9 为同一"操作安全性"相关簇（darwin HL-3）

### 补丁内容
- 【代码·技能缺陷】`ready_subtasks` 返回 `newly_skipped`；`cmd_step` 在 ready 为空时也 save + 打印 SKIPPED，修复 skipped 不持久化
- 【dim3·技能缺陷】新增「故障处理与失败模式」章节：6 行 if-then 四列表（现象→原因→一线修复→兜底）
- 【dim4·技能缺陷】新增 `🔴 CHECKPOINT · 执行前必须确认`（step 后确认上下文/工具、complete 前对照 success_criteria、reset 前确认）
- 【dim9·技能缺陷】新增「反例与黑名单」章节：7 条 ❌ 不要做什么

### 审计结果（独立复评 agent）
- 复评 96/100，dim3=12, dim4=6, dim5=17, dim7=11, dim9=6 均满分/近满分
- 实测：demo+validate、simple 闭环、complex 并行组同返+条件跳过（#8 skipped 已确认持久化）、5类失败模式错误可读且 exit code 合理、6项单测全过
- 通过率：触顶，无功能性硬伤

### 失败归因
- 全部为"技能缺陷"（文档缺失失败分支/检查点/黑名单 + 代码 skip 不落盘），属应改技能体

## 轮次 2 — 2026-07-12（applied, 96.0 → 96.0，触顶收尾）

### 补丁内容
- 【doc-drift·技能缺陷】`roadmap_schema.md` 的 status 字段删除误列的 `ready` 写入态，标注为"调度器内部态不写入文件"
- 【visibility】`cmd_step` 在 ready 非空时也打印 SKIPPED（之前仅 ready 为空时打印）

### 验证（用户直验，非独立agent）
- skip 与 ready 共存场景：同时打印 `SKIPPED #3` 与 `READY #2` ✓
- 6 项单测全过 ✓
- 分数已达天花板（Δ<2），按 HL-4 触顶停止，转入维护模式

## 维护模式约定
- 已达 96+，hill-climbing 边际收益递减；后续只修明确错误，不追分数
- 回归：保留 test-prompts.json，版本更新后重跑 `scripts/test_planner.py`
- 触发重新优化：外部依赖变化（新论文/新工具）、用户明确反馈问题、分数因外部因素降>5

## 独立第三方审计修复 — 2026-07-23（维护模式，不追分数）

独立 agent 深度审计（4维百分制：安全24/稳定23/维护18/兼容19=84分）。P0 0 项，P1 修复 5 项，P2 修复 5 项。

### P1 修复（真实缺陷）
- 【安全·M】validate 允许 `subtask_id=None` 进入 ids/id_map → 改 None/非 int 时 continue，防止后续 color dict 与错误信息混乱（planner.py validate）
- 【性能·M】ready_subtasks 中 `build_dag_info(data)` 调用返回值被丢弃（纯 O(n) 浪费）→ 删除该行
- 【可追溯·M】cmd_step 中 condition 不满足的 skipped 任务落盘但不写 trace → 新增 skip 事件到 trace
- 【可追溯·M】cmd_step 中 ready 任务入 running 不写 trace → 新增 step 事件到 trace
- 【安全·M】cmd_demo 默认文件名直接覆盖已存在文件 → 加入存在性检查，拒绝覆盖并提示指定 --out
- 【重构】抽取 `_trim_trace` helper，cmd_complete 与 cmd_step 统一调用，消除 trace 截断重复逻辑

### P2 修复（轻微/历史残留）
- results.tsv skill 列 `agentscope-meta-planner` → 更正为 `unclekk-roadmap-planner`
- references/audit-report-20260713.md 审计对象 → 标注历史命名/更名说明
- references/evolution-log.md 备份目录 → 标注已随更名归档、不在当前包内
- SKILL.md 文件锁 → 增加"同一 roadmap 文件必须由单一 Agent 顺序调用"约束
- _TRACE_MAX 截断语义 → 统一为 `_trim_trace` helper（注释语义自洽）

### 验证
- 6 项单测全过 ✓
- 无虚构断言：results.tsv 3 条评分行与 evolution-log 基线/轮次1/轮次2 一致 ✓
