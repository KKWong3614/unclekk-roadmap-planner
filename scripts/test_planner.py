#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unclekk-roadmap-planner 自测脚本。
运行方式：python scripts/test_planner.py
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLANNER = os.path.join(HERE, "planner.py")
PY = sys.executable


def run(*args, input_text=None):
    """调用 planner.py，返回 (stdout, stderr, returncode)。"""
    cmd = [PY, PLANNER] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, input=input_text)
    return proc.stdout, proc.stderr, proc.returncode


def new_tmp(suffix=""):
    fd, path = tempfile.mkstemp(suffix=suffix + ".json", prefix="test_")
    os.close(fd)
    return path


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_simple_mode():
    path = new_tmp("simple")
    _, err, rc = run("new", "--goal", "快速回答", "--mode", "simple", "--out", path)
    assert rc == 0, err
    data = load(path)
    assert data["mode"] == "simple"
    assert len(data["subtasks"]) == 1

    out, err, rc = run("step", path)
    assert rc == 0, err
    assert "READY #1" in out

    out, err, rc = run("complete", path, "--id", "1", "--output", "回答")
    assert rc == 0, err
    out, err, rc = run("step", path)
    assert rc == 0, err
    assert "ALL DONE" in out
    print("✓ simple_mode")


def test_validate_errors():
    # 非法 JSON
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        f.write("not json")
    _, err, rc = run("validate", path)
    assert rc != 0 and "不是合法 JSON" in err, err
    os.unlink(path)

    # 重复 id
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump({
            "goal": "g",
            "subtasks": [
                {"subtask_id": 1, "subtask_description": "a", "exact_input": "b", "expected_output": "c"},
                {"subtask_id": 1, "subtask_description": "a", "exact_input": "b", "expected_output": "c"},
            ]
        }, f)
    _, err, rc = run("validate", path)
    assert rc != 0 and "subtask_id 重复" in err, err
    os.unlink(path)

    # 环
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w") as f:
        json.dump({
            "goal": "g",
            "subtasks": [
                {"subtask_id": 1, "subtask_description": "a", "exact_input": "b", "expected_output": "c", "depends_on": [2]},
                {"subtask_id": 2, "subtask_description": "a", "exact_input": "b", "expected_output": "c", "depends_on": [1]},
            ]
        }, f)
    _, err, rc = run("validate", path)
    assert rc != 0 and "依赖图中存在环" in err, err
    os.unlink(path)
    print("✓ validate_errors")


def test_dag_and_parallel():
    path = new_tmp("dag")
    # 手动构造一个复杂 roadmap
    data = {
        "schema": "2.0",
        "goal": "测试 DAG + 并行组 + 条件",
        "mode": "complex",
        "subtasks": [
            {"subtask_id": 1, "subtask_description": "A", "exact_input": "", "expected_output": "", "depends_on": []},
            {"subtask_id": 2, "subtask_description": "B1", "exact_input": "", "expected_output": "", "depends_on": [1], "parallel_group": "p1"},
            {"subtask_id": 3, "subtask_description": "B2", "exact_input": "", "expected_output": "", "depends_on": [1], "parallel_group": "p1"},
            {"subtask_id": 4, "subtask_description": "C", "exact_input": "", "expected_output": "", "depends_on": [2, 3]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    _, err, rc = run("validate", path)
    assert rc == 0, err

    out, err, rc = run("step", path)
    assert rc == 0 and "READY #1" in out, err
    run("complete", path, "--id", "1", "--output", "a")

    out, err, rc = run("step", path)
    assert rc == 0 and "READY [2,3]" in out, out + err
    run("complete", path, "--id", "2", "--output", "b1")
    run("complete", path, "--id", "3", "--output", "b2")

    out, err, rc = run("step", path)
    assert rc == 0 and "READY #4" in out, out + err
    run("complete", path, "--id", "4", "--output", "c")

    out, err, rc = run("step", path)
    assert rc == 0 and "ALL DONE" in out, out + err
    print("✓ dag_and_parallel")


def test_condition_skip():
    path = new_tmp("cond")
    data = {
        "schema": "2.0",
        "goal": "测试条件跳过",
        "mode": "complex",
        "subtasks": [
            {"subtask_id": 1, "subtask_description": "A", "exact_input": "", "expected_output": "", "depends_on": []},
            {"subtask_id": 2, "subtask_description": "B", "exact_input": "", "expected_output": "", "depends_on": [1],
             "condition": 'len(outputs.get(1, "")) > 5'},
            {"subtask_id": 3, "subtask_description": "C", "exact_input": "", "expected_output": "", "depends_on": [2]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    run("step", path)
    run("complete", path, "--id", "1", "--output", "hi")  # 短，条件为假
    out, err, rc = run("step", path)
    assert rc == 0 and "READY #3" in out, out + err + "（#2 应被跳过）"
    data = load(path)
    assert data["subtasks"][1]["status"] == "skipped"
    print("✓ condition_skip")


def test_complete_order_guard():
    path = new_tmp("order")
    data = {
        "schema": "2.0",
        "goal": "测试乱序完成拦截",
        "mode": "complex",
        "subtasks": [
            {"subtask_id": 1, "subtask_description": "A", "exact_input": "", "expected_output": "", "depends_on": []},
            {"subtask_id": 2, "subtask_description": "B", "exact_input": "", "expected_output": "", "depends_on": [1]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    _, err, rc = run("complete", path, "--id", "2", "--output", "b")
    assert rc != 0 and "依赖 #1 尚未完成" in err, err
    print("✓ complete_order_guard")


def test_worker_assign():
    path = new_tmp("worker")
    run("new", "--goal", "w", "--out", path)
    _, err, rc = run("assign", path, "--id", "1", "--worker", "bob")
    assert rc == 0, err
    data = load(path)
    assert data["subtasks"][0]["assigned_worker"] == "bob"
    assert "bob" in data.get("worker_pool", {})
    print("✓ worker_assign")


def test_failed_reset_recovery():
    """failed 态 → reset 重置 → 重新 step → 成功 complete 闭环"""
    path = new_tmp("fail")
    data = {
        "schema": "2.0",
        "goal": "测试失败恢复",
        "mode": "complex",
        "subtasks": [
            {"subtask_id": 1, "subtask_description": "A", "exact_input": "", "expected_output": "",
             "success_criteria": "ok", "depends_on": []},
            {"subtask_id": 2, "subtask_description": "B", "exact_input": "", "expected_output": "",
             "success_criteria": "ok", "depends_on": [1]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # step 取 #1
    run("step", path)
    # 标记 failed（模拟执行失败）
    run("complete", path, "--id", "1", "--output", "error", "--status", "failed")
    d = load(path)
    assert d["subtasks"][0]["status"] == "failed"

    # 重置
    _, err, rc = run("reset", path, "--id", "1")
    assert rc == 0, err
    d = load(path)
    assert d["subtasks"][0]["status"] == "pending"

    # 重试
    out, err, rc = run("step", path)
    assert rc == 0 and "READY #1" in out, out + err
    run("complete", path, "--id", "1", "--output", "A 数据")

    out, err, rc = run("step", path)
    assert rc == 0 and "READY #2" in out, out + err
    run("complete", path, "--id", "2", "--output", "B 报告")

    out, err, rc = run("step", path)
    assert rc == 0 and "ALL DONE" in out, out + err
    print("✓ failed_reset_recovery")


def test_skip_force_recovery():
    """被 condition 跳过的任务，用 reset --force 可强制重跑（修复 R 项短板）"""
    path = new_tmp("skiprecover")
    data = {
        "schema": "2.0",
        "goal": "测试跳过任务强制恢复",
        "mode": "complex",
        "subtasks": [
            {"subtask_id": 1, "subtask_description": "A", "exact_input": "", "expected_output": "", "depends_on": []},
            {"subtask_id": 2, "subtask_description": "B", "exact_input": "", "expected_output": "", "depends_on": [1],
             "condition": 'len(outputs.get(1, "")) > 5'},
            {"subtask_id": 3, "subtask_description": "C", "exact_input": "", "expected_output": "", "depends_on": [2]},
        ]
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    run("step", path)
    run("complete", path, "--id", "1", "--output", "hi")  # 短产出，条件为假
    out, err, rc = run("step", path)          # #2 跳过，#3 被派发(running)
    assert rc == 0 and "READY #3" in out, out + err
    run("complete", path, "--id", "3", "--output", "C 先完成")  # 先收尾下游，避免卡在 running
    d = load(path)
    assert d["subtasks"][1]["status"] == "skipped"

    # 不用 force：reset 后再次 step，#2 仍会被条件跳过
    run("reset", path, "--id", "2")
    out, err, rc = run("step", path)
    assert rc == 0, out + err
    d = load(path)
    assert d["subtasks"][1]["status"] == "skipped", "未用 --force 时 #2 应保持跳过"

    # 用 force：reset --force 后 #2 可强制重跑
    run("reset", path, "--id", "2", "--force")
    out, err, rc = run("step", path)
    assert rc == 0 and "READY #2" in out, out + err + "（--force 应让 #2 可重跑）"
    run("complete", path, "--id", "2", "--output", "B 产出（强制重跑）")
    out, err, rc = run("step", path)
    assert rc == 0 and "ALL DONE" in out, out + err
    print("✓ skip_force_recovery")


def main():
    tests = [
        test_simple_mode,
        test_validate_errors,
        test_dag_and_parallel,
        test_condition_skip,
        test_complete_order_guard,
        test_worker_assign,
        test_failed_reset_recovery,
        test_skip_force_recovery,
    ]
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"✗ {t.__name__}: {e}")
            sys.exit(1)
    print(f"\n全部 {len(tests)} 项测试通过。")


if __name__ == "__main__":
    main()
