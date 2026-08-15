# UncleKK Roadmap Planner · 先规划后执行编排器

> 依据论文 Meta Planner 模块实现的"先规划、再执行"编排器：DAG 依赖调度、并行组、条件跳过、Worker 分配、可审计可恢复。
>
> A "plan-first, execute-later" orchestrator based on the Meta Planner module from the AgentScope 1.0 paper: DAG dependency scheduling, parallel groups, conditional skips, Worker assignment, auditable and resumable.

依据 AgentScope 1.0 论文 Meta Planner 模块设计的"先规划、再执行"编排器。
支持复杂任务的 DAG 依赖调度、并行组、条件跳过、Worker 分配、工具组合提示、
持久状态与任务恢复。本技能是编排器，不直接调用 LLM；真正的 Worker 执行由调用 Agent 完成。

An orchestrator designed after the Meta Planner module of the AgentScope 1.0 paper, following a "plan first, then execute" approach.
It supports DAG dependency scheduling, parallel groups, conditional skips, Worker assignment, and tool-combination hints for complex tasks, plus persistent state and task recovery. This skill is an orchestrator and does not call the LLM directly; the actual Worker execution is performed by the invoking agent.

解决的问题：
- Agent 拿到复杂任务就闷头死磕、方向跑偏。
- 多步骤任务上下文断裂、无法接力。
- 任务执行不可见、不可调试、不可恢复。

Problems it solves:
- Agents dive head-first into complex tasks and drift off course.
- Multi-step tasks lose context and can't be handed off.
- Task execution is invisible, undebuggable, and unrecoverable.

触发条件：复杂多步骤任务、需要先规划再执行、需要把大目标拆成可审计子任务、
写长文/做研究/搭流程/多 Agent 协作编排。

When to use: complex multi-step tasks, when you need to plan before executing, or need to break a large goal into auditable subtasks — writing long-form content, doing research, building pipelines, or orchestrating multi-agent collaboration.

关键词：Meta Planner、Roadmap、任务分解、DAG、并行组、条件跳过、WorkerManager、
工具分配、先规划后执行、可审计、可恢复。

Keywords: Meta Planner, Roadmap, task decomposition, DAG, parallel groups, conditional skip, WorkerManager, tool assignment, plan-first-execute-later, auditable, resumable.

## 安装 Installation

将此技能克隆到你的 WorkBuddy 技能目录：
Clone this skill into your WorkBuddy skills directory:

```bash
git clone https://github.com/KKWong3614/unclekk-roadmap-planner.git "$HOME/.workbuddy/skills/unclekk-roadmap-planner"
```

或下载 Release 中的 zip，解压到技能目录即可。
Or download the zip from the Release and extract it into your skills directory.

## 目录结构 Directory Structure

```
unclekk-roadmap-planner/
├── SKILL.md      # 技能主文件（含 frontmatter）
├── README.md     # 本文件
├── LICENSE       # MIT 许可证
├── references/   # 参考文档（如有）
├── scripts/      # 可执行脚本（如有）
└── templates/    # 模板（如有）
```

## 版本 Version

当前版本：`2.0.1`
Current version: `2.0.1`

## 许可证 License

[MIT](LICENSE) © 2026 KK大叔 (UncleKK)
