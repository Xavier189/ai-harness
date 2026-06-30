#!/usr/bin/env python3
"""ai-harness 行为 eval runner（纯标准库）。

声明式：每个场景是 evals/scenarios/*.json，描述
  - setup: 在临时目录预先写入的文件
  - steps: 顺序执行的 harness 子命令
  - expect: 收尾断言（文件存在/不存在、文件内容包含/不包含、exit 码、stdout 包含）

不依赖 unittest，直接 `python3 evals/run.py` 跑。失败返回非零退出码并打印第一处不匹配。
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import io
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS = importlib.machinery.SourceFileLoader(
    "harness_cli", str(ROOT / "ai_harness.py")
).load_module()


def run_cmd(repo_root: Path, args: list[str]) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = HARNESS.main(["--root", str(repo_root), *args])
    return code, buf.getvalue()


def assert_expect(repo_root: Path, expect: dict, last_code: int, last_out: str) -> list[str]:
    failures: list[str] = []
    if "exit" in expect and last_code != expect["exit"]:
        failures.append(f"exit: 期望 {expect['exit']}，实际 {last_code}")
    for rel in expect.get("file_exists", []):
        if not (repo_root / rel).exists():
            failures.append(f"file_exists: 缺少 {rel}")
    for rel in expect.get("file_absent", []):
        if (repo_root / rel).exists():
            failures.append(f"file_absent: 不应存在 {rel}")
    for rel, needle in expect.get("file_contains", {}).items():
        path = repo_root / rel
        if not path.exists():
            failures.append(f"file_contains: 缺少 {rel}")
            continue
        if needle not in path.read_text(encoding="utf-8"):
            failures.append(f"file_contains: {rel} 未包含 {needle!r}")
    for rel, needle in expect.get("file_not_contains", {}).items():
        path = repo_root / rel
        if path.exists() and needle in path.read_text(encoding="utf-8"):
            failures.append(f"file_not_contains: {rel} 不应包含 {needle!r}")
    for needle in expect.get("stdout_contains", []):
        if needle not in last_out:
            failures.append(f"stdout_contains: 未出现 {needle!r}")
    return failures


def run_scenario(scenario_path: Path) -> tuple[bool, list[str]]:
    spec = json.loads(scenario_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, body in spec.get("setup", {}).items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
        last_code, last_out = 0, ""
        for step in spec.get("steps", []):
            last_code, last_out = run_cmd(root, step)
        failures = assert_expect(root, spec.get("expect", {}), last_code, last_out)
    return not failures, failures


def main() -> int:
    scenarios_dir = ROOT / "evals/scenarios"
    if not scenarios_dir.exists():
        print(f"没有场景目录：{scenarios_dir}")
        return 0
    files = sorted(scenarios_dir.glob("*.json"))
    if not files:
        print("没有可运行的 .json 场景")
        return 0
    total, passed = 0, 0
    for path in files:
        total += 1
        ok, failures = run_scenario(path)
        if ok:
            passed += 1
            print(f"  PASS  {path.name}")
        else:
            print(f"  FAIL  {path.name}")
            for f in failures:
                print(f"        - {f}")
    print(f"\n{passed}/{total} 场景通过")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
