# unclekk Roadmap Planner

> 依据论文 Meta Planner 模块实现的"先规划、再执行"编排器：DAG 依赖调度、并行组、条件跳过、Worker 分配、可审计可恢复。

依据 AgentScope 1.0 论文 Meta Planner 模块设计的"先规划、再执行"编排器。
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

## 安装

将此技能克隆到你的 WorkBuddy 技能目录：

```bash
git clone https://github.com/KKWong3614/unclekk-roadmap-planner.git "$HOME/.workbuddy/skills/unclekk-roadmap-planner"
```

或下载 Release 中的 zip，解压到技能目录即可。

## 目录结构

```
unclekk-roadmap-planner/
├── SKILL.md      # 技能主文件（含 frontmatter）
├── README.md     # 本文件
├── LICENSE       # MIT 许可证
├── references/   # 参考文档（如有）
├── scripts/      # 可执行脚本（如有）
└── templates/    # 模板（如有）
```

## 版本

当前版本：`2.0.1`

## 许可证

[MIT](LICENSE) © 2026 KK大叔 (UncleKK)
