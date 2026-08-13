# Post-Audit 修复验证报告 (2026-07-13)

> 基于 audit-report-20260713.md 的 P1→P2 修复 + 运行时验证。
> 主 Hermes 执行修复（审计铁律：审计长只报告不修复，修复由主进程负责）。

## 修改文件
- `scripts/planner.py`：P1-1, P2-1, P2-3, P2-4, P2-5
- `SKILL.md`：P1-2, P2-6

## 修复清单与验证

| ID | 修复 | 验证方法 | 结果 |
|---|---|---|---|
| P1-1 | `_sanitize_path()` 加到 load()/save() 入口，拒绝 `..` 遍历 | 静态检查 | ✓ |
| P1-2 | SKILL.md "动态 Worker 实例化" → "Worker 分配记录" | 静态检查（措辞已收敛） | ✓ |
| P2-1 | 删除 `import time` 死代码 | AST 确认 time 未使用 | ✓ |
| P2-3 | save() `except Exception` → `except OSError` | 静态检查（L88 已收窄） | ✓ |
| P2-4 | failed 态差异化：complete/status/summary 三处 | 静态检查三处含 "失败"/"✗" | ✓ |
| P2-5 | trace 轮转：`_TRACE_MAX=500` + `trace[:] = trace[-499:]` | 静态检查 | ✓ |
| P2-6 | SKILL.md "文件说明" 标注残留工件用途 | 静态检查 | ✓ |

## 运行时验证
```
$ python scripts/test_planner.py
✓ simple_mode
✓ validate_errors
✓ dag_and_parallel
✓ condition_skip
✓ complete_order_guard
✓ worker_assign
全部 6 项测试通过。
```

## 说明
- P1-1 最初采用"脚本目录树白名单"，但测试用 tempfile 目录（不在脚本目录树）导致失败。已收敛为"拒绝显式 `..` 遍历"，与 Hermes Agent 调用上下文下"路径由调用者传入"的信任模型一致，既不阻塞正常使用又能防御最直接的遍历攻击。
- P2-2（文档冗余）：经核实 SKILL.md 的字段说明是"用法示例"而非 schema 定义，与 roadmap_schema.md 不构成真正冗余，未修改。
- L247 `except Exception as e` 是 `eval_condition` 把非法条件表达式转为可读错误的设计，属合理使用，不在修复范围。

---
修复时间: 2026-07-13
