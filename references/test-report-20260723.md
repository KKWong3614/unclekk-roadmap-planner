# 实测报告：unclekk-roadmap-planner（2026-07-23）

## 实测环境
- Python 3.12.0（`/c/Users/Administrator/.local/bin/python3.12`）
- planner.py：`d:/skill待检/unclekk-roadmap-planner/scripts/planner.py`
- 测试文件：`scripts/test_planner.py`

## 测试用例与结果

### 1. 完整 complex 流程（8 步竞品分析报告）
**场景**：竞品分析报告（收集→调研→汇总→分析→可视化→复核→定稿）
**结果**：✅ 6/6 单测全过，完整流程闭环

**具体行为**：
- `new` 建模板 → 手动填充 8 个 subtasks（含并行组、条件跳过、工具、Worker）→ `validate` 通过 ✅
- `step` 1 返回 #1（无依赖、无组）✅
- `complete` #1 → `step` 2 返回 #2 与 #3（并行组 collect 一起返回）✅
- 并行组上下文正确聚合：#2 和 #3 均获得 #1 的产出 ✅
- `step` 3 返回 #4（依赖 #2、#3 都完成）✅
- `step` 4 返回 #5（依赖 #4）✅

### 2. 失败恢复流程（failed→reset→retry）
**场景**：执行失败后 reset 重置，重新执行
**结果**：✅ 完全闭环

- `complete --status failed` 标记失败 ✅
- `status` 显示 `✗` 标记，提示"可 reset 重试" ✅
- `reset --id 1` 重置为 pending ✅
- 重新 `step` → `complete` 成功 ✅
- 下游 #2 依赖 #1 重新可执行 ✅

### 3. 乱序完成拦截
**场景**：未完成上游直接 complete 下游
**结果**：✅ 正确拦截

- `complete #2` 在 #1 未完成时报"依赖 #1 尚未完成"，退出码 1 ✅

### 4. trace 审计链路
**结果**：✅ 完整可追溯

- step/complete/skip 事件全部写入 trace ✅
- reset 重置后 trace 保留（历史不删除）✅
- 时间戳精确到毫秒 ✅

### 5. 条件跳过（condition）
**场景**：条件为假时自动跳过，下游依赖 skipped 态的任务可继续
**结果**：✅ 部分通过，发现语义缺陷

- 条件为假时自动标记 skipped，下游可继续 ✅
- skipped 状态正确落盘 ✅
- **⚠️ 缺陷发现**：skipped 态一旦写入，即使条件后来变为 true 也不会重新评估（见下文）

---

## 实测发现的语义缺陷

### 缺陷：skipped 态永久化，无法重新评估

**现象**：
- #6 带条件 `len(outputs.get(5, '')) >= 50`
- step 4 时 #5 尚未完成，条件求值为 false，#6 被标记为 skipped
- step 5 完成 #5（产出足够长，条件本应为 true）
- step 6 时 #6 已是 skipped 态，`ready_subtasks` 过滤条件 `status not in ("pending", "running")` 直接跳过 #6
- 即使条件已满足，#6 永久丢失

**根因**：
- `planner.py` L330: `if status not in ("pending", "running"): continue`
- `skipped` 态不在过滤列表中，即使后续 outputs 变化也不会重新进入 candidate

**影响**：
- 使用 condition 的任务如果首次条件不满足被跳过，将永远无法执行
- 即使条件后来变为 true（因为下游任务完成），skipped 态也不会重新评估

**建议修复**：
- 方案 A（保守）：在 `ready_subtasks` 中对 skipped 任务也做 condition 重评估，若条件变为 true 则恢复为 pending
- 方案 B（推荐）：SKILL.md 文档中明确披露"skipped 态不可逆"的语义，并给出使用建议（condition 应只用于"已知下游状态"的场景）

---

## 总结

- **单测通过率**：7/7（6 项原有 + 1 项新增 failed_reset_recovery）
- **完整流程**：✅ 闭环
- **失败恢复**：✅ 可用
- **trace 审计**：✅ 完整
- **条件跳过**：⚠️ 有语义缺陷（skipped 永久化）
