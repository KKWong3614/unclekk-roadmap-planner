# Changelog · 更新日志

> 中文优先版（skillhub）。所有版本均经 `python scripts/test_planner.py` 自测通过。

## 2.1.1（2026-09-03）· 补齐文档

- 新增 `README.md`（中文优先·skillhub 版，小白友好）：30 秒上手、受众、自动触发、硬代码保障、跳过恢复坑点、审计报告样例、文档导航。
- 新增 `README.github.md`（英文优先·GitHub 版），已在 `README.md` 引用，消除孤立文档。
- 新增 `CHANGELOG.md`：版本历史与版本规则。
- 版本号三处一致（SKILL.md / _meta.json / CHANGELOG.md）→ 2.1.1；无代码变更，自测 8/8 通过。

## 2.1.0（2026-09-02）· 响应 TRACE 测评改进

- **修复"被 condition 跳过的任务无法重跑"**（R 项 4.5 核心短板）：新增 `reset --id N --force` + `forced` 字段，强制重跑被条件跳过的任务；`complete` 后自动清零。
- **修复 `attempts` 无限膨胀**：`ready_subtasks` 不再把 `running` 态任务重复派发。
- **严格闭环兜底**：依赖 `failed` → 下游级联 `failed`，不死锁。
- **步数限制硬代码**：新增 `MAX_ATTEMPTS=5`、`MAX_SUBTASKS=1000` 兜底。
- **文档对齐规则**：双语标题、受众分层（新手→专业）、最小可运行示例、自动触发阈值、FAQ 坑点、审计报告样例、硬代码保障清单；新增 `README.md` 与 `CHANGELOG.md`。
- **显示名**：skillhub `displayName` 改为 `UncleKK Roadmap Planner`。

## 2.0.0（早期版本）

- 双模式（simple / complex）、DAG 依赖调度、并行组 fan-out/fan-in。
- 条件跳过（`condition`）、Worker 分配、工具组合提示。
- 原子写、错误处理、路径防护、任务可恢复。

## 版本规则（Versioning）

- 主版本 `.0`：架构/接口不兼容变更。
- 次版本 `.x`：新增能力或重要修复（如 2.1.0 的 `--force`）。
- 修订号：仅文档/文案微调时递增。
- 每次发布版本号须 **高于** 线上版本，且 `SKILL.md` frontmatter、`_meta.json`、`CHANGELOG.md` 三处一致。
