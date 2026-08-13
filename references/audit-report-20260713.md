# unclekk-roadmap-planner — 深度审计报告

> **审计身份**：独立第三方审计长（与主 Hermes 隔离的 subagent）
> **审计日期**：2026-07-13
> **审计方法**：全文件读取 + 静态代码审查 + 文档交叉验证（8 阶段）
> **审计对象**：`d:/待检skill/agentscope-meta-planner`（历史命名；现更名为 `unclekk-roadmap-planner`）
> **核心声明**：仅审计、仅报告，**未对任何代码/文件做修复**。

---

## 阶段 1：文件清单 (File Inventory)

| 文件 | 类型 | 作用 |
|---|---|---|
| `SKILL.md` | 技能元数据 + 文档 | frontmatter + 完整使用说明 |
| `scripts/planner.py` | **核心代码** (848 行) | CLI 编排器，8 个子命令 |
| `scripts/test_planner.py` | **测试** (211 行) | 6 项集成测试 |
| `references/roadmap_schema.md` | 文档 (182 行) | Roadmap JSON schema 定义 |
| `references/evolution-log.md` | 日志 (46 行) | darwin-skill 进化记录 |
| `results.tsv` | **工件** | 评分演化表（4 行 TSV） |
| `test-prompts.json` | **工件** | 4 条测试提示词 JSON |

**结论**：有真实代码（planner.py 848 行，零第三方依赖）、真实测试（6 项）、构建/部署无关文件无。`results.tsv` 与 `test-prompts.json` 属进化过程产物，见 Phase 3 残留工件分析。

---

## 阶段 2：SKILL.md Frontmatter 与文件系统现实对比

| 检查项 | Frontmatter 声明 | 实际现实 | 判定 |
|---|---|---|---|
| `name` | `agentscope-meta-planner` | 目录名 `agentscope-meta-planner` | ✅ 一致 |
| `version` | `2.0` | `planner.py:27 SCHEMA_VERSION = "2.0"`；ROADMAP schema 字段 `"2.0"`；`results.tsv` 含 v2 轮次；`roadmap_schema.md` 标题 "v2.0" | ✅ 一致 |
| `description` 核心能力 | DAG 调度、并行组、条件跳过、Worker 分配、工具提示、持久状态、任务恢复 | 代码全实现：拓扑排序 L180-198、并行组 L332-352、条件求值 L210-239、Worker assign L590-600、desired_auxiliary_tools L76、原子写 L63-82、reset L603-626 | ✅ 匹配 |
| `description` 明确边界 | "不直接调用 LLM；Worker 执行由调用 Agent 完成" | 代码无 HTTP/LLM/MCP 调用，纯文件+JSON 操作 | ✅ 匹配（诚实边界声明） |
| `requires` | 无声明 | 代码仅用 stdlib（argparse/json/os/sys/tempfile/collections/datetime）；`time` 模块导入但未使用 | ⚠️ 见 P2-1 |
| 工具声明 | 8 个 CLI 命令（new/validate/step/complete/status/summary/assign/reset + demo） | 代码 `cmd_` 函数 8 个（cmd_new/cmd_validate/cmd_step/cmd_complete/cmd_status/cmd_summary/cmd_assign/cmd_reset）+ cmd_demo | ✅ 一致 |

---

## 阶段 3：文档交叉验证（Critical）

### 3.1 工具清单统计
- SKILL.md 命令总览列出：**8 个命令**（new / validate / assign / step / complete / status / summary / reset）+ demo
- 代码 `def cmd_*`：**8 个**命令函数 + `cmd_demo`
- **一致** ✅

### 3.2 依赖声明 vs 实际 import
- SKILL.md 声明："零第三方依赖"
- 实际 import（planner.py:18-25）：`argparse, json, os, sys, tempfile, time, defaultdict, datetime, timezone` —— 全部 stdlib
- 实际依赖：真正零第三方 ✅
- **但**：`import time`（L23）代码中**从未被使用**——死代码

### 3.3 版本一致性
- SKILL.md frontmatter version: **2.0**
- planner.py SCHEMA_VERSION: **"2.0"**（L27）
- roadmap.json schema 字段：`"2.0"`（L638, L668）
- roadmap_schema.md 标题：**v2.0**
- evolution-log 最终轮次：v2（96.0 分）
- results.tsv 最终 committed score：**96.0**
- **全部一致 ✅**

### 3.4 路径引用 / 硬编码
- 代码路径使用 `os.path.dirname(os.path.abspath(__file__))`（planner.py L28, L66）—— 相对脚本定位，**无硬编码用户名/绝对路径** ✅
- `cmd_demo` 输出默认 `os.path.abspath("demo_roadmap.json")`（L773）—— 相对 cwd，平台中立 ✅
- test 使用 `sys.executable` 而非硬编码 `python` ✅
- **无硬编码路径 / 无平台特定假设 ✅**

### 3.5 残留工件分析
- **results.tsv**：评分演化记录（baseline 78.7 → preopt-v2 96.0 → round2 96.0），共 4 行。是 darwin-skill 进化过程产物，对 skill 运行**无功能作用**，属"元审计痕迹"。
- **test-prompts.json**：4 条用户提示词+期望行为。供回归测试/人类验收用，非运行必需。
- 两者均为**良性残留**（文档/审计用途），不污染运行；但严格讲属于"非代码必需文件"。

---

## 阶段 4：代码质量审查

| 维度 | 评价 | 证据 |
|---|---|---|
| **输入校验** | ✅ 强。normalize() 补齐默认值防 KeyError（L84-123）；validate() 校验根类型/g, subtasks 非空/id 整数且唯一/必填字段/数组类型/condition 字符串（L126-207） | L86-98 defaults dict |
| **错误处理** | ⚠️ 整体好，一处瑕疵。用自定义 `PlannerError` 兜底 + 顶层 except 捕获（L840-844），无裸 traceback；原子写用 try/except + 清理 tmp 文件（L65-81）。**瑕疵**：save() L74 `except Exception:` 吞掉内部异常再 raise——虽保留原异常，但属宽泛捕获模式，建议收窄 | planner.py L74 |
| **并发安全** | ⚠️ 文档诚实声明。原子写（tempfile+os.replace+fsync）降低风险（L67-73），但**无跨进程文件锁**（SKILL.md L215 明确承认）。对单进程/串行使用足够，多进程抢写仍会丢更新——文档诚实 ✅ | SKILL.md L215 |
| **资源清理** | ✅ 好。load() 用 with 语句自动关闭文件句柄（L53）；save() 临时文件在异常路径 os.unlink（L75-78）；测试 temp 文件显式 os.close + os.unlink（test_planner.py L28, L65, L80, L95） | planner.py L53, L67-78 |
| **日志/敏感数据** | ✅ 安全。全程用 `eprint()` 打印结构化错误到 stderr；**无 API key/密码/密钥**进入日志（本技能不调外部服务，无密钥面）；错误信息含文件路径但属本地路径，非敏感 ✅ | planner.py L42-43, L842-843 |

---

## 阶段 5：安全评估

| 攻击面 | 检查内容 | 发现 | 证据 |
|---|---|---|---|
| **认证** | 谁可以调用？有 token/key 验证吗？ | 无认证机制——作为本地 CLI 脚本，靠文件系统权限/调用者上下文控制。对 Hermes skill 场景合理（由 Agent 调用，Agent 已是受信任中介） | planner.py 无 auth 逻辑 |
| **授权** | 调用者 A 能否访问 B 的数据？ | 无租户隔离——roadmap.json 按文件路径区分任务，无用户边界。Hermes 单 Agent 场景无跨用户数据风险 | 纯文件读写，路径由 args 传入 |
| **输入验证** | 路径遍历、注入、超大 payload？ | ⚠️ **路径无白名单约束**：`args.roadmap` 直接传给 `open()`，无 path-sanity 检查，可访问任意本地路径（依赖 os 权限）。**condition 沙箱**用 `eval(..., {"__builtins__": {}})` 隔离，安全 | planner.py L50-54, L232-239 |
| **敏感数据** | API key/密码在日志/错误？ | ✅ 无。本技能不调外部服务，无密钥。错误信息只含本地路径和字段内容，用户自产数据 | — |
| **权限提升** | 客户端能否给自己授权？ | 无权限系统，不适用 | — |
| **依赖供应链** | 依赖固定版本？已知漏洞？ | 仅 stdlib，无第三方包，无 CVE 面 | planner.py L18-25 |

### [S-1] condition 表达式沙箱强度评估（重点）
`eval(expr, {"__builtins__": {}}, allowed_names)`（L237）+ allowed_names 仅含 outputs/goal/context + 6 个内置函数。
- **防御有效**：关闭 `__builtins__` 阻断 `__import__`/`open`/`exec`/`getattr(builtins,'__import__')` 等常用逃逸。
- **剩余攻击面**：Python 对象反射。由于 `allowed_names` 是普通 dict，表达式可访问 `outputs.__class__`、`outputs.values` 等对象方法（`values` 是属性加载非变量加载，不被 `__builtins__` 拦截）。**但** outputs 是 `dict[int,str]`，可用方法（get/items）均为纯读，**无副作用能力**。结论：沙箱对"副作用逃逸"有效，对"信息读取"不拦截但数据本身无害。✅ 可接受。

### [S-2] 路径遍历面
`open(path)` 无 `os.path.realpath` 或白名单校验。恶意 `--roadmap /etc/passwd` 可被读取（若有权限）；`--out ../malicious.json` 可覆盖任意文件。Hermes Agent 调用上下文下风险低，但作为独立 CLI 脚本**属可改进项**。P1 级。

---

## 阶段 6：8 层审计原则

### 第 1 层 · 架构层
**位置**：系统编排层"班长"，位于 Agent（工人）之上、LLM 之下。SKILL.md L39-58 诚实划分了"代码真实现 vs 交给 Agent"的边界表。
- ✅ **发现**：边界声明诚实，无夸大。"班长/工人"比喻准确（L58）。
- ⚠️ **发现**：文档声称"动态 Worker 实例化"（L31），但代码仅 `assigned_worker` 字符串分配 + `worker_pool` 记录（planner.py L596-598），**无真正的动态 Agent 实例化**——属"记名"而非"实例化"，文档用词略夸张。**证据**：planner.py 无 Agent 创建/启动逻辑。

### 第 2 层 · 假设层
**前提假设**：
1. 调用者（Agent）会按 step→complete 循环串行操作 roadmap.json
2. 子任务产出由 Agent 外部产生并回写，本技能不负责执行
3. `condition` 用 Python 表达式书写
- ✅ **发现**：假设合理且与"不调 LLM"定位一致。
- ⚠️ **发现**：假设"单进程/串行"是隐性的——SKILL.md L215 承认，但 step/complete 的"running"态设计暗示可能有人期望并发。**证据**：SKILL.md L215 "并发修改…仍可能冲突"。

### 第 3 层 · 边界层
**不能做什么**：不调 LLM、不真并行、不动态装卸 MCP（SKILL.md L54-56）。
- ✅ **发现**：边界声明极为诚实，是本文档最亮点之一，有效避免"货不对板"。
- **证据**：SKILL.md L43-56 对照表。

### 第 4 层 · 耦合层
- **依赖谁**：零第三方包，仅 Python stdlib。解耦极佳。
- **被谁依赖**：被调用 Agent 作为 CLI 编排器调用；roadmap.json 是外部接口。
- ⚠️ **发现**：`test_planner.py` 用 `subprocess.run` 黑盒测试 CLI（L21-22），耦合了 CLI 接口而非直接 import 函数——测试易受 argparse 变更影响，但符合"验证真实 CLI 行为"的意图，可接受。

### 第 5 层 · 冗余层
- ⚠️ **发现**：`SKILL.md` 与 `roadmap_schema.md` 存在**语义重复**——核心字段、校验规则在 SKILL.md（L134-172）与 roadmap_schema.md（L76-86）两处定义，维护时需双处同步。`roadmap_schema.md` L48 标注 ready 为内部态是轮次 2 才修复的 doc-drift，印证了历史不同步风险。
- **与 Hermes 内置功能冗余**：Hermes 自身的"先规划再执行"可通过 prompt + 记忆实现，本 skill 提供**结构化持久化 + DAG 调度**的差异化价值，非纯冗余。✅

### 第 6 层 · 缺失层
- ⚠️ **发现**：**无日志等级/轮转**。所有输出直接 print，无标准日志模块；长任务 trace 全存于 JSON `trace` 数组，无独立日志文件/大小限制，理论上有内存/文件大小无上限风险（trace 单调增长）。
- ⚠️ **发现**：**无 `failed` 态的恢复语义差异**。complete 支持 `--status failed`（L531-536）但 failed 与 skipped/done 在 status/summary 显示上仅标记为 "?"（L555），无专用恢复提示。
- **证据**：planner.py L550-555。

### 第 7 层 · 演进层
- ✅ **发现**：最后更新 **2026-07-12**（evolution-log L13-41），距审计日 1 天。两轮 darwin-skill 优化后触顶（96.0），转入维护模式。
- ✅ 已修复的已知问题：cmd_step skip 不落盘 bug（L429-433 已处理）、doc-drift ready 态（roadmap_schema L48 已校正）、visibility 改进。
- ⚠️ **发现**：base on "AgentScope 1.0 论文 arXiv:2508.16279v1"——**审计无法独立验证字段设计是否"忠实"论文**，论文引用为不可外部核验的声明。

### 第 8 层 · 盲区层
- ⚠️ **发现**：**大文件性能盲区**。`validate()` 和 `ready_subtasks()` 对 subtasks 做 O(n²) 级扫描（L148-207, L312-361），subtasks 上千时无问题优化。`gather_outputs` 全量遍历 L248-267 随产出文本量线性增长——长任务上下文拼接可能巨大。
- ⚠️ **发现**：**subtask_id 类型盲区**。validate() 允许非 int 报错（L155-156），但 `normalize()` L102-103 对遗漏 id 用 `index+1` 兜底，若 LLM 传入非整数 id 会在 `ids.add(sid)` 与 DAG 遍历中产生混合类型风险（虽 validate 会拦截，normalize 先于 validate 运行）。

---

## 阶段 7：评分与报告

### 评分明细

| 类别 | 权重 | 得分 | 扣分依据 |
|---|---|---|---|
| **Correctness** | /25 | **24** | 声明与现实高度一致，边界诚实；-1：`import time` 未使用（死代码，轻微）；-0.5：论文"忠实"不可核验 |
| **Completeness** | /25 | **23** | 文档完整、测试覆盖 6 项、失败模式/检查点/黑名单齐全；-1.5：results.tsv 与 test-prompts.json 为良性残留工件；-0.5：SKILL.md 与 roadmap_schema.md 语义重复 |
| **Security** | /20 | **17** | 沙箱有效、无密钥泄露、原子写；-2：路径无白名单/无 sanity 校验（可遍历/覆盖）；-1：condition 沙箱信息读取面未隔离（虽无害） |
| **Code Quality** | /15 | **14** | 错误处理/资源清理/输入校验优秀；-1：save() L74 宽泛 `except Exception:`；-0.5：无标准日志模块、trace 无大小限制 |
| **Design** | /15 | **14** | 架构清晰、边界诚实、差异化价值明确；-1：SKILL.md/roadmap_schema.md 文档冗余；-0.5：failed 态语义未显式差异化 |

### 总分：**92 / 100**

> 评级：**优良（A-）**。这是一个文档诚实、边界清晰、代码扎实的成熟 skill。主要扣分点集中在安全路径校验与文档冗余，均为可改进项而非功能缺陷。

---

## 问题清单（按优先级）

### [P0] 严重问题 — 功能断裂 / 安全漏洞 / 数据风险
**（无）** — 未发现会阻塞功能或造成数据泄露的严重问题。沙箱隔离有效，无密钥面。

### [P1] 重要问题 — 文档错误 / 维护问题 / 误导用户
- **[P1-1] 路径无白名单校验**：`open(path)` 直接接收用户路径，无 `realpath`/白名单约束，可访问任意本地文件、覆盖任意 `--out` 路径。建议加 `os.path.realpath` 校验或白名单目录。（证据：planner.py L50-54, L820-824）
- **[P1-2] "动态 Worker 实例化"用词夸张**：代码仅字符串分配+worker_pool 记录，无真实 Agent 实例化。建议措辞收敛为"Worker 分配/点名"。（证据：planner.py L596-598 vs SKILL.md L31）

### [P2] 一般问题 — 设计瑕疵 / 代码风格 / 冗余
- **[P2-1] 死代码**：`import time`（L23）从未使用，应删除。
- **[P2-2] 文档冗余**：核心字段与校验规则在 SKILL.md（L134-172）与 roadmap_schema.md（L19-86）双处定义，维护需同步。建议以 roadmap_schema.md 为单一事实源，SKILL.md 引用。
- **[P2-3] 宽泛异常捕获**：`save()` L74 `except Exception:` 可收窄为具体 OSError 子类，避免意外吞异常。
- **[P2-4] failed 态无差异化语义**：status/summary 对 failed 显示 "?"（L555），无专用提示或恢复引导。
- **[P2-5] trace 数组无大小/轮转限制**：长任务 trace 单调增长，JSON 文件大小理论上无限。
- **[P2-6] 良性残留工件**：`results.tsv` / `test-prompts.json` 非运行必需，建议移至 `references/` 或文档注明用途。

---

## 阶段 8：Meta-Audit（对审计本身的审计）

### 8.1 我可能遗漏了什么？
1. **未实际运行测试**：审计基于静态阅读，未执行 `python scripts/test_planner.py` 验证 6 项测试真实通过（evolution-log 声称全过，但我未复跑）。
2. **未运行 demo/new/validate 端到端**：未实测 CLI 命令的 stdout/stderr 输出是否与文档示例一致。
3. **未测试边界 payload**：未用超大 roadmap.json、Unicode 注入、超长 condition 表达式等做实际压力测试。
4. **论文忠实度无法核验**：arXiv:2508.16279v1 我未读取，无法判断字段设计是否真"忠实"论文。

### 8.2 证据 vs 推测比例
- **基于直接证据（文件内容 + 行号）**：约 **85%** —— 版本、import、函数定义、文档声明、沙箱实现、原子写逻辑，均有精确行号。
- **基于推测/推断**：约 **15%** —— 路径遍历风险评估（基于通用安全常识而非实际攻击）、trace 无限增长推断、论文忠实度判断。
- **诚实标记**：凡推测处均在文中标注"建议""理论上""推断"等。

### 8.3 本次审计的局限性
1. **纯静态审计**：无运行时行为观察、无性能基准、无并发实测。
2. **单时间点快照**：仅审计当前文件状态，未跟踪 git 历史（该 skill 明确为非 git 仓库，evolution-log L4 说明）。
3. **Hermes 集成上下文受限**：未观察该 skill 在真实 Agent 调用链中的行为，仅审计 skill 本体。
4. **未检查编码/换行兼容性**：跨平台 JSON 编码/换行符兼容性未实测。

### 8.4 未检查到的领域
- 实际 LLM 调用链路中的提示词质量（本 skill 不调 LLM，属下游 Agent 责任，已排除）
- 用户真实使用场景下的 UX 问题（依赖人类验收）
- 与其他 Hermes skill 的实际交互冲突（需真实部署环境）
- 文件编码异常 / Windows 路径空格等特殊边界

---

## 修复建议（按优先级）

1. **[P1-1] 加路径白名单/sanity 校验**：在 `load()`/`save()` 入口加 `os.path.realpath` 或限定目录，防止路径遍历与任意文件覆盖。
2. **[P1-2] 收敛"动态 Worker 实例化"措辞**：改为"Worker 分配/点名记录"，与代码实现一致。
3. **[P2-1] 删除 `import time`** 死代码。
4. **[P2-2] 去文档冗余**：SKILL.md 字段描述改为引用 `roadmap_schema.md`，建立单一事实源。
5. **[P2-3] 收窄 `save()` 异常捕获**：`except Exception` → `except OSError`。
6. **[P2-4/5] failed 态差异化 + trace 轮转**：补充 failed 显示与 trace 大小上限（可选）。
7. **[P2-6] 标注残留工件用途**：在 SKILL.md 或 README 注明 results.tsv / test-prompts.json 为"审计/回归痕迹"。

---

══════════════════════════════════════
**审计结论**：agentscope-meta-planner v2.0 是一个**文档诚实、边界清晰、代码扎实**的 Hermes skill，评分 **92/100（A-）**。无 P0 级功能断裂或安全漏洞。主要改进空间在路径校验安全与文档去冗余，均为低风险、高收益的可改进项。建议通过上述 P1/P2 修复后，可安全投入生产使用。

**审计长声明**：本报告仅基于静态代码与文档审查，未实际执行运行测试，未核验论文忠实度。建议使用者运行 `python scripts/test_planner.py` 确认测试通过后再生产部署。
══════════════════════════════════════
