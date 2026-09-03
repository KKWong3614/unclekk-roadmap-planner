#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unclekk-roadmap-planner v2.1
===========================
依据 AgentScope 1.0 论文 Meta Planner 模块的忠实实现：

- 双模式：simple（轻量 ReAct 单步）/ complex（完整 planning-execution）
- RoadmapManager：结构化 Roadmap，子任务含依赖(depends_on)与成功标准(success_criteria)
- WorkerManager：worker 分配(assigned_worker) + 工具组合分配(desired_auxiliary_tools)
- 调度器：DAG 拓扑排序、并行组(parallel_group)、条件跳过(condition)、上下文按依赖聚合
- 持久状态：JSON 落盘 + 原子写 + 时间戳/尝试次数/trace
- 可恢复：reset 子任务（含 --force 强制重跑被条件跳过的任务），支持调试与任务续跑
- 硬代码兜底（v2.1 新增）：MAX_ATTEMPTS 防死循环、MAX_SUBTASKS 防超大文件、
  依赖失败级联失败保证严格闭环、路径遍历拒绝、condition 沙箱求值

本技能是编排器，不直接调用 LLM。真正的 Worker 执行由调用 Agent 完成。
"""

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone

SCHEMA_VERSION = "2.0"
HERE = os.path.dirname(os.path.abspath(__file__))

# ── 硬代码兜底保障（Hard-coded safeguards，v2.1 新增/强化）──────────
MAX_ATTEMPTS = 5      # 单任务最大重试次数；超过需 reset 才能再跑，防止死循环
MAX_SUBTASKS = 1000   # 单 roadmap 子任务数上限，防止异常超大文件拖垮调度
_TRACE_MAX = 500      # trace 事件数上限，防止 JSON 文件无限增长

# 论文未指定字段名，下列字段是把论文概念落地后的 JSON 设计：
# - subtask_description / exact_input / expected_output / success_criteria
#   对应论文 "executable subtasks with defined dependencies and success criteria"
# - desired_auxiliary_tools 对应论文 "specialized toolkit allocation"
# - depends_on 对应论文 "defined dependencies"
# - assigned_worker 对应论文 "dynamic worker agent instantiation"
# - forced (v2.1) 用于绕过 condition，强制重跑被条件跳过的任务


class PlannerError(Exception):
    """可预期的规划错误，避免裸 traceback。"""


def eprint(*a):
    print(*a, file=sys.stderr)

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def _trim_trace(trace: list) -> None:
    """将 trace 截断到最近 _TRACE_MAX 条（原地，留 1 条空间给本次追加）。"""
    if len(trace) >= _TRACE_MAX:
        trace[:] = trace[-_TRACE_MAX + 1:]


def _sanitize_path(path: str) -> str:
    """规范化路径，拒绝显式 .. 遍历。
    注意：不做 realpath 解析，避免 msys/WSL /tmp 路径被跨层映射到 Windows 盘符。
    """
    if os.path.pardir in os.path.normpath(path):
        raise PlannerError(f"拒绝显式 .. 遍历路径: {path}")
    return os.path.abspath(path)

def load(path):
    """加载 roadmap JSON，带统一错误处理。"""
    path = _sanitize_path(path)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise PlannerError(f"找不到 roadmap 文件: {path}")
    except json.JSONDecodeError as e:
        raise PlannerError(f"roadmap 文件不是合法 JSON ({path}): {e}")
    except OSError as e:
        raise PlannerError(f"无法读取 roadmap 文件 ({path}): {e}")


def save(path, data):
    """原子写：先写临时文件，再 os.replace，降低并发/崩溃时文件损坏概率。"""
    path = _sanitize_path(path)
    try:
        dir_name = os.path.dirname(os.path.abspath(path)) or "."
        fd, tmp = tempfile.mkstemp(dir=dir_name, suffix=".tmp", prefix=".roadmap-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except OSError as e:
        raise PlannerError(f"无法保存 roadmap 文件 ({path}): {e}")


def normalize_subtask(s, index):
    """给 subtask 补全可选字段默认值，避免下游 KeyError。"""
    defaults = {
        "success_criteria": "",
        "desired_auxiliary_tools": [],
        "depends_on": [],
        "parallel_group": None,
        "condition": None,
        "assigned_worker": None,
        "status": "pending",
        "output": "",
        "started_at": None,
        "completed_at": None,
        "attempts": 0,
        "forced": False,
    }
    for k, v in defaults.items():
        s.setdefault(k, v)
    # 保证有 id（允许 LLM 偶尔遗漏时按位置兜底，但 validate 会进一步检查）
    if "subtask_id" not in s:
        s["subtask_id"] = index + 1
    return s


def normalize(data):
    """补全顶层与子任务默认值，保证任意入口拿到的结构一致。"""
    if not isinstance(data, dict):
        raise PlannerError("roadmap 根节点必须是 JSON 对象")
    data.setdefault("schema", SCHEMA_VERSION)
    data.setdefault("based_on", "AgentScope 1.0 Meta Planner")
    data.setdefault("mode", "complex")
    data.setdefault("context", {})
    data.setdefault("worker_pool", {})
    data.setdefault("trace", [])
    data.setdefault("created_at", now_iso())
    data.setdefault("updated_at", data.get("created_at", now_iso()))
    subs = data.get("subtasks", [])
    if not isinstance(subs, list):
        raise PlannerError("subtasks 必须是数组")
    data["subtasks"] = [normalize_subtask(s, i) for i, s in enumerate(subs)]
    return data


def validate(data):
    """
    校验 roadmap：字段、依赖、DAG 无环、parallel_group 一致性、mode 约束、规模上限。
    返回错误列表（空表示通过）。
    """
    errors = []
    if not isinstance(data, dict):
        return ["roadmap 根节点必须是 JSON 对象"]
    if not data.get("goal"):
        errors.append("缺少 goal")

    subs = data.get("subtasks")
    if not isinstance(subs, list) or len(subs) == 0:
        errors.append("subtasks 必须是非空数组")
        return errors

    if len(subs) > MAX_SUBTASKS:
        errors.append(f"subtasks 数量({len(subs)})超过上限 {MAX_SUBTASKS}")

    mode = data.get("mode", "complex")
    if mode not in ("simple", "complex"):
        errors.append(f"mode 必须是 simple 或 complex，当前: {mode}")

    ids = set()
    id_map = {}
    for i, s in enumerate(subs):
        if not isinstance(s, dict):
            errors.append(f"subtasks[{i}] 必须是对象")
            continue
        sid = s.get("subtask_id")
        if sid in ids:
            errors.append(f"subtask_id 重复: {sid}")
        if not isinstance(sid, int) or sid is None:
            errors.append(f"subtasks[{i}].subtask_id 缺失或不是整数")
            continue
        ids.add(sid)
        id_map[sid] = i
        for k in ("subtask_description", "exact_input", "expected_output"):
            if k not in s:
                errors.append(f"subtask_id={sid} 缺少字段 {k}")
        for k in ("depends_on", "desired_auxiliary_tools"):
            v = s.get(k)
            if v is not None and not isinstance(v, list):
                errors.append(f"subtask_id={sid} 的 {k} 必须是数组")
        pg = s.get("parallel_group")
        if pg is not None and not isinstance(pg, str):
            errors.append(f"subtask_id={sid} 的 parallel_group 必须是字符串或 null")
        cond = s.get("condition")
        if cond is not None and not isinstance(cond, str):
            errors.append(f"subtask_id={sid} 的 condition 必须是字符串表达式或 null")

    # 依赖必须指向存在的子任务
    for s in subs:
        for dep in s.get("depends_on", []):
            if dep not in id_map:
                errors.append(f"subtask_id={s['subtask_id']} 依赖不存在的子任务: {dep}")

    # DAG 无环检测
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {s["subtask_id"]: WHITE for s in subs}

    def dfs(sid):
        color[sid] = GRAY
        for dep in subs[id_map[sid]].get("depends_on", []):
            if dep not in color:
                continue
            if color[dep] == GRAY:
                errors.append(f"依赖图中存在环，涉及 subtask_id={sid}")
                return False
            if color[dep] == WHITE and not dfs(dep):
                return False
        color[sid] = BLACK
        return True

    for s in subs:
        if color[s["subtask_id"]] == WHITE:
            dfs(s["subtask_id"])

    # simple 模式约束：只能有 1 步且无依赖
    if mode == "simple":
        if len(subs) != 1:
            errors.append("mode=simple 时 subtasks 必须且只能有 1 个")
        if subs[0].get("depends_on"):
            errors.append("mode=simple 时不允许有依赖")

    return errors


def safe_eval_condition(expr, outputs, goal, context):
    """
    安全评估 condition 表达式。可用变量:
        outputs: dict[int, str]  已完成子任务的产出
        goal:    str             顶层目标
        context: dict            顶层上下文
    可用函数: len, bool, str, int, float, any, all
    """
    if not expr or not expr.strip():
        return True
    allowed_names = {
        "outputs": outputs,
        "goal": goal,
        "context": context,
        "len": len,
        "bool": bool,
        "str": str,
        "int": int,
        "float": float,
        "any": any,
        "all": all,
    }
    try:
        code = compile(expr, "<condition>", "eval")
        # 关闭 __builtins__，只允许访问 allowed_names 中的变量/函数。
        # 属性名（如 outputs.get 中的 get）不是变量加载，无需显式放行；
        # 若被当作变量使用则会触发 NameError，自然被拒绝。
        return eval(code, {"__builtins__": {}}, allowed_names)
    except Exception as e:
        raise PlannerError(f"condition 表达式求值失败 ({expr}): {e}")


def gather_outputs(data, upto_id=None, dep_ids=None):
    """
    组装前置上下文。
    - 如果指定 dep_ids：按依赖聚合（忠实论文"defined dependencies"）
    - 否则：聚合所有已完成且 id < upto_id 的产出（向后兼容顺序执行）
    """
    outputs = {}
    for s in data["subtasks"]:
        if s.get("status") == "done" and s.get("output"):
            outputs[s["subtask_id"]] = s["output"]

    if dep_ids:
        ctx = []
        for did in dep_ids:
            dep = next((x for x in data["subtasks"] if x["subtask_id"] == did), None)
            if dep and dep.get("output"):
                ctx.append(f"[#{dep['subtask_id']} {dep['subtask_description']}]\n{dep['output']}")
        return outputs, "\n\n".join(ctx)

    ctx = []
    for s in data["subtasks"]:
        if upto_id is not None and s["subtask_id"] >= upto_id:
            break
        if s.get("status") == "done" and s.get("output"):
            ctx.append(f"[#{s['subtask_id']} {s['subtask_description']}]\n{s['output']}")
    return outputs, "\n\n".join(ctx)


def build_dag_info(data):
    """构建依赖 DAG 的辅助结构。"""
    subs = data["subtasks"]
    id_map = {s["subtask_id"]: i for i, s in enumerate(subs)}
    in_degree = defaultdict(int)
    downstream = defaultdict(list)
    for s in subs:
        sid = s["subtask_id"]
        deps = s.get("depends_on", []) or []
        in_degree[sid] = len(deps)
        for d in deps:
            downstream[d].append(sid)
    return id_map, in_degree, downstream


def ready_subtasks(data):
    """
    返回当前可执行的子任务列表（已按 DAG 展开、条件求值、并行组聚合）。
    规则：
    1. 仅 status=pending（含被条件恢复 / forced 的）进入候选，running 不重复派发
    2. 依赖全部完成(done)或被跳过(skipped)才可执行；依赖中有 failed → 级联标记 failed（兜底闭环）
    3. condition 表达式为假 → skipped；forced=True 可绕过 condition
    4. 同一 parallel_group 的任务一起返回
    返回 (ready_items, newly_skipped, newly_failed)
    """
    subs = data["subtasks"]
    finished_ids = {s["subtask_id"] for s in subs if s.get("status") in ("done", "skipped")}
    failed_ids = {s["subtask_id"] for s in subs if s.get("status") == "failed"}

    def deps_satisfied(s):
        return all(d in finished_ids for d in (s.get("depends_on", []) or []))

    outputs, _ = gather_outputs(data)
    goal = data.get("goal", "")
    context = data.get("context", {})

    candidates = []        # ("ready", s)
    newly_skipped = []     # 本次新标记为 skipped 的子任务
    newly_failed = []      # 本次级联失败：(s, failed_dep_ids)

    for s in subs:
        status = s.get("status")

        # 被跳过的任务：带 condition 且条件后来变真 → 恢复为 pending 重新执行
        if status == "skipped":
            cond = s.get("condition")
            if cond:
                try:
                    if safe_eval_condition(cond, outputs, goal, context):
                        s["status"] = "pending"
                        s.pop("completed_at", None)
                        finished_ids.discard(s["subtask_id"])
                        candidates.append(("ready", s))
                        continue
                except PlannerError:
                    raise
            # 仍 skipped：保持，不派发
            continue

        # running / failed 不进入候选（running 由 cmd_step 报告 WAITING）
        if status in ("running", "failed"):
            continue
        if status != "pending":
            continue

        deps = s.get("depends_on", []) or []
        # 兜底：硬依赖失败 → 级联失败，避免死锁，保证严格闭环
        failed_deps = [d for d in deps if d in failed_ids]
        if failed_deps:
            s["status"] = "failed"
            s["completed_at"] = now_iso()
            newly_failed.append((s, failed_deps))
            continue

        if not deps_satisfied(s):
            continue

        cond = s.get("condition")
        forced = s.get("forced", False)
        try:
            if cond and not forced and not safe_eval_condition(cond, outputs, goal, context):
                # 条件不满足 → 标记为 skipped（幂等），并视为依赖已满足供下游使用
                s["status"] = "skipped"
                s["completed_at"] = now_iso()
                finished_ids.add(s["subtask_id"])
                newly_skipped.append(s)
                continue
        except PlannerError:
            raise
        candidates.append(("ready", s))

    # 按 parallel_group 聚合：
    # - 无并行组的任务直接加入 ready_items
    # - 有并行组的任务：只有当整组所有尚未完成的成员都满足依赖时，才把整个组加入 ready_items
    group_members = defaultdict(list)
    ready_items = []
    for kind, s in candidates:
        pg = s.get("parallel_group")
        if pg:
            group_members[pg].append(s)
        else:
            ready_items.append(s)

    candidate_ids = {x["subtask_id"] for _, x in candidates}
    for pg, members in group_members.items():
        # 找出该组所有尚未完成的成员
        all_unfinished = [x for x in subs if x.get("parallel_group") == pg and x.get("status") in ("pending", "running")]
        # 若所有未完成成员都在候选集（依赖已满足），则整组返回
        if all(m["subtask_id"] in candidate_ids for m in all_unfinished):
            ready_items.extend(members)

    # 去重并排序（按 subtask_id 稳定顺序）
    seen = set()
    result = []
    for s in sorted(ready_items, key=lambda x: x["subtask_id"]):
        if s["subtask_id"] not in seen:
            result.append(s)
            seen.add(s["subtask_id"])
    return result, newly_skipped, newly_failed


def cmd_new(args):
    data = {
        "schema": SCHEMA_VERSION,
        "based_on": "AgentScope 1.0 Meta Planner",
        "goal": args.goal,
        "mode": args.mode,
        "context": {},
        "worker_pool": {},
        "subtasks": [
            {
                "subtask_id": 1,
                "subtask_description": "<由 Agent 用 LLM 依据 goal 拆解后填写>",
                "exact_input": "<本子任务的精确输入，可引用前序产出>",
                "expected_output": "<期望产出，需能喂给下一步>",
                "success_criteria": "<如何判断这一步算完成>",
                "desired_auxiliary_tools": [],
                "depends_on": [],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            }
        ],
        "trace": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    save(args.out, data)
    eprint(f"已创建 roadmap 模板: {args.out}")
    if args.mode == "complex":
        eprint("下一步：用 LLM 把 subtasks 拆成完整 Roadmap（参考 SKILL.md 拆解要点），再运行 validate。")
    else:
        eprint("mode=simple：直接编辑唯一子任务并执行 step → complete。")


def cmd_validate(args):
    data = normalize(load(args.roadmap))
    errs = validate(data)
    if errs:
        eprint("校验失败:")
        for e in errs:
            eprint("  - " + e)
        sys.exit(1)
    eprint("校验通过 ✓")


def cmd_step(args):
    data = normalize(load(args.roadmap))
    errs = validate(data)
    if errs:
        eprint("校验失败，无法 step:")
        for e in errs:
            eprint("  - " + e)
        sys.exit(1)

    ready, newly_skipped, newly_failed = ready_subtasks(data)

    # 持久化本轮的状态转移（skip / 级联失败），保证可追溯
    if newly_skipped or newly_failed:
        trace = data.setdefault("trace", [])
        _trim_trace(trace)
        for s in newly_skipped:
            trace.append({"event": "skip", "subtask_id": s["subtask_id"], "reason": "condition_unsatisfied", "at": now_iso()})
        for s, deps in newly_failed:
            trace.append({"event": "fail", "subtask_id": s["subtask_id"], "reason": "dep_failed:" + str(deps), "at": now_iso()})
        data["updated_at"] = now_iso()
        save(args.roadmap, data)
        for s in newly_skipped:
            print(f"SKIPPED #{s['subtask_id']} {s['subtask_description']}（条件不满足，已跳过）")
        for s, deps in newly_failed:
            print(f"FAILED #{s['subtask_id']} {s['subtask_description']}（依赖 {deps} 失败，已级联标记失败 → 需 reset 恢复）")

    if not ready:
        running = [s for s in data["subtasks"] if s.get("status") == "running"]
        if running:
            print("WAITING：以下子任务正在执行中，等待 complete:")
            for s in running:
                print(f"  #{s['subtask_id']} {s['subtask_description']} (worker={s.get('assigned_worker') or '未分配'})")
            return
        pending = [s for s in data["subtasks"] if s.get("status") == "pending"]
        if pending:
            eprint("当前没有可执行的子任务：部分 pending 子任务的依赖尚未完成，或条件不满足。可 `reset --id N --force` 强制重跑被跳过的任务。")
            sys.exit(1)
        print("ALL DONE ✓")
        return

    # 派发前兜底盘查：超过重试上限的任务不派发，需 reset 后才能再跑
    dispatchable = []
    for s in ready:
        if s.get("attempts", 0) >= MAX_ATTEMPTS:
            eprint(f"⚠ 任务 #{s['subtask_id']} 已达重试上限({MAX_ATTEMPTS})，未派发；请 `reset --id {s['subtask_id']}` 后重试。")
            continue
        dispatchable.append(s)
    if not dispatchable:
        running = [s for s in data["subtasks"] if s.get("status") == "running"]
        if running:
            print("WAITING：有任务正在执行中，等待 complete。")
            return
        eprint("没有可派发的子任务（部分已达重试上限，需 reset）。")
        sys.exit(1)

    # 标记为 running 并派发
    for s in dispatchable:
        s["status"] = "running"
        s["started_at"] = now_iso()
        s["attempts"] = s.get("attempts", 0) + 1
        if args.worker:
            s["assigned_worker"] = args.worker
            data.setdefault("worker_pool", {})[args.worker] = {"assigned_at": now_iso()}

    data["updated_at"] = now_iso()
    # 记录 ready 事件到 trace，保证调度步骤可追溯
    trace = data.setdefault("trace", [])
    _trim_trace(trace)
    for s in dispatchable:
        trace.append({
            "event": "step",
            "subtask_id": s["subtask_id"],
            "status": "running",
            "at": now_iso(),
        })
    save(args.roadmap, data)

    # 输出 READY 信息
    if len(dispatchable) == 1:
        print(f"READY #{dispatchable[0]['subtask_id']}: {dispatchable[0]['subtask_description']}")
    else:
        ids = ",".join(str(s["subtask_id"]) for s in dispatchable)
        descs = " / ".join(s["subtask_description"] for s in dispatchable)
        print(f"READY [{ids}]: {descs}")

    for s in dispatchable:
        outputs, ctx = gather_outputs(data, dep_ids=s.get("depends_on", []))
        print(f"\n--- subtask #{s['subtask_id']} ---")
        print(f"描述: {s['subtask_description']}")
        print(f"精确输入: {s['exact_input']}")
        print(f"期望产出: {s['expected_output']}")
        if s.get("success_criteria"):
            print(f"成功标准: {s['success_criteria']}")
        print(f"工具组合: {s.get('desired_auxiliary_tools') or []}")
        if s.get("assigned_worker"):
            print(f"已分配 Worker: {s['assigned_worker']}")
        if s.get("parallel_group"):
            print(f"并行组: {s['parallel_group']}")
        if s.get("condition"):
            tag = "（已强制重跑，忽略条件）" if s.get("forced") else ""
            print(f"执行条件: {s['condition']}{tag}")
        if ctx:
            print("\n前置上下文（来自依赖项产出）:")
            print(ctx)
        else:
            print("\n前置上下文: [无]")


def cmd_complete(args):
    data = normalize(load(args.roadmap))
    errs = validate(data)
    if errs:
        eprint("校验失败，无法 complete:")
        for e in errs:
            eprint("  - " + e)
        sys.exit(1)

    target = next((s for s in data["subtasks"] if s["subtask_id"] == args.id), None)
    if target is None:
        eprint(f"未找到 subtask_id={args.id}")
        sys.exit(1)

    # 校验：依赖必须已完成或被跳过（skipped 视为已完成但无产出）
    finished_ids = {s["subtask_id"] for s in data["subtasks"] if s.get("status") in ("done", "skipped")}
    for dep in target.get("depends_on", []):
        if dep not in finished_ids:
            eprint(f"无法完成 #{args.id}：依赖 #{dep} 尚未完成")
            sys.exit(1)

    # 校验：当前任务必须是 running 或 pending（不能完成已经 done/skipped 的）
    if target.get("status") not in ("pending", "running"):
        eprint(f"无法完成 #{args.id}：当前状态为 {target.get('status')}，不能重复完成")
        sys.exit(1)

    target["status"] = args.status
    target["output"] = args.output if args.output is not None else ""
    target["completed_at"] = now_iso()
    target["forced"] = False  # 完成后清除强制标记

    # 记录 trace（限制最大事件数，防止 JSON 文件无限增长）
    trace = data.setdefault("trace", [])
    _trim_trace(trace)
    trace.append({
        "event": "complete",
        "subtask_id": args.id,
        "status": args.status,
        "worker": target.get("assigned_worker"),
        "at": now_iso(),
    })
    data["updated_at"] = now_iso()
    save(args.roadmap, data)

    if args.status == "done":
        eprint(f"子任务 #{args.id} 已完成并记录。")
    elif args.status == "skipped":
        eprint(f"子任务 #{args.id} 已标记为跳过。")
    elif args.status == "failed":
        eprint(f"子任务 #{args.id} 执行失败（下游将级联失败；可 reset 后重试）。")
    else:
        eprint(f"子任务 #{args.id} 状态更新为 {args.status}。")


def cmd_status(args):
    data = normalize(load(args.roadmap))
    total = len(data["subtasks"])
    counts = defaultdict(int)
    for s in data["subtasks"]:
        counts[s.get("status", "pending")] += 1
    eprint(f"目标: {data['goal']}")
    eprint(f"模式: {data.get('mode', 'complex')}")
    eprint(f"进度: done={counts['done']}/{total}, running={counts['running']}, skipped={counts['skipped']}, failed={counts['failed']}, pending={counts['pending']}")
    eprint("-" * 40)
    for s in data["subtasks"]:
        mark = {
            "done": "✓",
            "running": "▶",
            "skipped": "⊘",
            "failed": "✗",
            "pending": " ",
        }.get(s.get("status"), "?")
        if s.get("status") == "failed":
            eprint(f" [{mark}] #{s['subtask_id']} {s['subtask_description']} [w:{s.get('assigned_worker')}] ← 执行失败，可 reset 重试")
            continue
        worker = f" [w:{s.get('assigned_worker')}]" if s.get("assigned_worker") else ""
        pg = f" [pg:{s.get('parallel_group')}]" if s.get("parallel_group") else ""
        eprint(f" [{mark}] #{s['subtask_id']} {s['subtask_description']}{worker}{pg}")


def cmd_summary(args):
    data = normalize(load(args.roadmap))
    total = len(data["subtasks"])
    done = sum(1 for s in data["subtasks"] if s.get("status") == "done")
    print(f"目标: {data['goal']}")
    print(f"模式: {data.get('mode', 'complex')}")
    print(f"进度: {done}/{total}")
    print("-" * 40)
    for s in data["subtasks"]:
        mark = {
            "done": "✓",
            "running": "▶",
            "skipped": "⊘",
            "failed": "✗",
            "pending": "○",
        }.get(s.get("status"), "?")
        worker = f" [w:{s.get('assigned_worker')}]" if s.get("assigned_worker") else ""
        if s.get("status") == "failed":
            print(f" [{mark}] #{s['subtask_id']} {s['subtask_description']}{worker} ← 失败，可 reset")
        else:
            print(f" [{mark}] #{s['subtask_id']} {s['subtask_description']}{worker}")
        if s.get("status") == "done" and s.get("output"):
            out = s["output"]
            if len(out) > 200:
                out = out[:200] + " …(截断)"
            print(f"     产出: {out}")
    if data.get("trace"):
        print("-" * 40)
        print("执行 trace:")
        for t in data["trace"]:
            print(f"  {t['at']} | {t['event']} #{t['subtask_id']} {t['status']}")


def cmd_assign(args):
    data = normalize(load(args.roadmap))
    target = next((s for s in data["subtasks"] if s["subtask_id"] == args.id), None)
    if target is None:
        eprint(f"未找到 subtask_id={args.id}")
        sys.exit(1)
    target["assigned_worker"] = args.worker
    data.setdefault("worker_pool", {})[args.worker] = {"assigned_at": now_iso()}
    data["updated_at"] = now_iso()
    save(args.roadmap, data)
    eprint(f"子任务 #{args.id} 已分配给 worker: {args.worker}")


def cmd_reset(args):
    data = normalize(load(args.roadmap))
    if args.id is None:
        for s in data["subtasks"]:
            s["status"] = "pending"
            s["output"] = ""
            s["started_at"] = None
            s["completed_at"] = None
            s["attempts"] = 0
            s["forced"] = False
        data["trace"] = []
        eprint("所有子任务已重置为 pending（forced 已清除）。")
    else:
        target = next((s for s in data["subtasks"] if s["subtask_id"] == args.id), None)
        if target is None:
            eprint(f"未找到 subtask_id={args.id}")
            sys.exit(1)
        target["status"] = "pending"
        target["output"] = ""
        target["started_at"] = None
        target["completed_at"] = None
        target["attempts"] = 0
        target["forced"] = bool(args.force)
        if args.force:
            eprint(f"子任务 #{args.id} 已重置为 pending，并标记 forced（将忽略 condition 强制重跑）。")
        else:
            eprint(f"子任务 #{args.id} 已重置为 pending。")
    data["updated_at"] = now_iso()
    save(args.roadmap, data)


def demo_roadmap():
    """竞品报告生成示例，展示依赖、并行组、条件跳过。"""
    return {
        "schema": SCHEMA_VERSION,
        "based_on": "AgentScope 1.0 Meta Planner",
        "goal": "撰写一份关于竞品分析工具市场的竞品报告",
        "mode": "complex",
        "context": {"market": "AI 竞品分析工具", "report_style": "数据驱动、结论先行"},
        "worker_pool": {},
        "subtasks": [
            {
                "subtask_id": 1,
                "subtask_description": "锁定 3-5 个核心竞品",
                "exact_input": "目标市场=AI 竞品分析工具；筛选维度=功能覆盖、价格、目标用户",
                "expected_output": "竞品清单（含名称、官网、一句话定位）",
                "success_criteria": "清单不少于 3 个且每个竞品有明确定位",
                "desired_auxiliary_tools": ["search"],
                "depends_on": [],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 2,
                "subtask_description": "收集竞品公开信息",
                "exact_input": "使用 #1 的竞品清单，分别抓取官网定价、核心功能、用户评价",
                "expected_output": "每个竞品的结构化信息卡片",
                "success_criteria": "每个竞品至少覆盖定价、核心功能、用户评价三个维度",
                "desired_auxiliary_tools": ["search", "browser"],
                "depends_on": [1],
                "parallel_group": "collect",
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 3,
                "subtask_description": "收集市场宏观数据",
                "exact_input": "搜索 AI 竞品分析工具市场规模、增长趋势、用户画像",
                "expected_output": "市场宏观数据摘要（规模、趋势、用户画像）",
                "success_criteria": "有关键数字和来源",
                "desired_auxiliary_tools": ["search"],
                "depends_on": [1],
                "parallel_group": "collect",
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 4,
                "subtask_description": "拆解对比维度",
                "exact_input": "综合 #2 和 #3 的产出，确定 4-6 个对比维度（如功能、价格、易用性、生态）",
                "expected_output": "对比维度表及每个维度的评判标准",
                "success_criteria": "维度可量化或可明确比较",
                "desired_auxiliary_tools": [],
                "depends_on": [2, 3],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 5,
                "subtask_description": "逐项对比打分",
                "exact_input": "按 #4 维度，对 #1 清单中的竞品逐项打分并附依据",
                "expected_output": "对比矩阵（竞品 × 维度）及打分依据",
                "success_criteria": "每个维度每个竞品都有分数和一句话依据",
                "desired_auxiliary_tools": [],
                "depends_on": [4],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 6,
                "subtask_description": "识别差异化机会",
                "exact_input": "基于 #5 对比矩阵，找出市场空白或我方可切入的差异化点",
                "expected_output": "2-3 个差异化机会点及可行性判断",
                "success_criteria": "机会点有数据或对比结果支撑",
                "desired_auxiliary_tools": [],
                "depends_on": [5],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 7,
                "subtask_description": "撰写报告正文",
                "exact_input": "整合 #5 对比矩阵与 #6 差异化机会，按报告结构写作",
                "expected_output": "竞品报告正文（含摘要、对比、结论、建议）",
                "success_criteria": "结构完整、结论有数据支撑、字数适中",
                "desired_auxiliary_tools": [],
                "depends_on": [5, 6],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 8,
                "subtask_description": "补充数据可视化",
                "exact_input": "从 #5 对比矩阵中提取关键数据，生成 1-2 张图表",
                "expected_output": "图表文件路径或嵌入代码",
                "success_criteria": "图表能直观支撑报告核心结论",
                "desired_auxiliary_tools": ["chart"],
                "depends_on": [5],
                "parallel_group": None,
                "condition": 'len(outputs.get(5, "")) > 50',
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
            {
                "subtask_id": 9,
                "subtask_description": "复核与定稿",
                "exact_input": "对 #7 报告和 #8 图表做事实核查、格式统一、结论一致性检查",
                "expected_output": "终稿报告 + 复核清单（通过/未通过）",
                "success_criteria": "无事实错误、格式统一、结论一致",
                "desired_auxiliary_tools": [],
                "depends_on": [7, 8],
                "parallel_group": None,
                "condition": None,
                "assigned_worker": None,
                "status": "pending",
                "output": "",
                "forced": False,
            },
        ],
        "trace": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cmd_demo(args):
    out = args.out or os.path.abspath("demo_roadmap.json")
    if os.path.exists(out):
        eprint(f"拒绝覆盖已存在文件: {out}（请指定 --out 为其他路径）")
        sys.exit(1)
    data = demo_roadmap()
    save(out, data)
    eprint(f"已生成示例 roadmap: {out}")
    errs = validate(data)
    if errs:
        eprint("示例校验失败: " + "; ".join(errs))
        sys.exit(1)
    eprint("示例校验通过 ✓")
    cmd_summary(argparse.Namespace(roadmap=out))


def main():
    p = argparse.ArgumentParser(
        description="unclekk-roadmap-planner v2.1: AgentScope 1.0 Meta Planner 风格的任务分解与编排器"
    )
    sub = p.add_subparsers(dest="cmd")

    sp = sub.add_parser("new", help="新建 roadmap 模板")
    sp.add_argument("--goal", required=True)
    sp.add_argument("--mode", choices=["simple", "complex"], default="complex")
    sp.add_argument("--out", default="roadmap.json")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("validate", help="校验 roadmap")
    sp.add_argument("roadmap")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("step", help="取下一个/组可执行子任务 + 前置上下文")
    sp.add_argument("roadmap")
    sp.add_argument("--worker", help="指定执行该子任务的 worker 名称")
    sp.set_defaults(func=cmd_step)

    sp = sub.add_parser("complete", help="标记子任务完成/跳过/失败并记录产出")
    sp.add_argument("roadmap")
    sp.add_argument("--id", type=int, required=True)
    sp.add_argument("--output", default="")
    sp.add_argument("--status", choices=["done", "skipped", "failed"], default="done")
    sp.set_defaults(func=cmd_complete)

    sp = sub.add_parser("status", help="打印当前进度")
    sp.add_argument("roadmap")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("summary", help="打印完整 trace 与产出")
    sp.add_argument("roadmap")
    sp.set_defaults(func=cmd_summary)

    sp = sub.add_parser("assign", help="分配 worker 到子任务（WorkerManager）")
    sp.add_argument("roadmap")
    sp.add_argument("--id", type=int, required=True)
    sp.add_argument("--worker", required=True)
    sp.set_defaults(func=cmd_assign)

    sp = sub.add_parser("reset", help="重置子任务状态（支持任务恢复/调试）")
    sp.add_argument("roadmap")
    sp.add_argument("--id", type=int, help="只重置指定子任务；省略则重置全部")
    sp.add_argument("--force", action="store_true",
                    help="强制重跑：忽略 condition 并把任务标记为可重新执行（用于恢复被条件跳过的任务）")
    sp.set_defaults(func=cmd_reset)

    sp = sub.add_parser("demo", help="生成竞品报告示例 roadmap（默认写到当前目录）")
    sp.add_argument("--out", help="输出路径，默认 ./demo_roadmap.json")
    sp.set_defaults(func=cmd_demo)

    args = p.parse_args()
    if not getattr(args, "cmd", None):
        p.print_help()
        sys.exit(1)
    try:
        args.func(args)
    except PlannerError as e:
        eprint(f"错误: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
