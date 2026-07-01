from __future__ import annotations

import contextlib
import importlib.machinery
import io
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = ROOT / "ai_harness.py"
harness = importlib.machinery.SourceFileLoader("harness_cli", str(HARNESS_PATH)).load_module()


class HarnessCliTest(unittest.TestCase):
    def run_cli(self, root: Path, *args: str) -> int:
        return harness.main(["--root", str(root), *args])

    def run_cli_capture(self, root: Path, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = harness.main(["--root", str(root), *args])
        return code, buffer.getvalue()

    def test_init_core_generates_expected_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = self.run_cli(root, "init", "--profile", "core", "--agent", "codex,claude")

            self.assertEqual(code, 0)
            self.assertTrue((root / "docs/ai-harness/STATE.md").exists())
            self.assertTrue((root / ".harness/state.yml").exists())
            self.assertTrue((root / ".harness/phases/current/PLAN.md").exists())
            self.assertIn("AI-HARNESS:ROUTER:START", (root / "AGENTS.md").read_text())
            self.assertIn("AI-HARNESS:ROUTER:START", (root / "CLAUDE.md").read_text())

    def test_init_preserves_existing_agent_file_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("# 既有内容\n\n保留这段。\n", encoding="utf-8")

            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            first = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("保留这段。", first)
            self.assertEqual(first.count("AI-HARNESS:ROUTER:START"), 1)

            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            second = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(second.count("AI-HARNESS:ROUTER:START"), 1)

    def test_java_spring_profile_only_adds_policy_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "java-spring", "--agent", "codex"), 0)

            policies = (root / "docs/ai-harness/POLICIES.md").read_text(encoding="utf-8")
            self.assertIn("Java/Spring Profile", policies)
            self.assertFalse((root / "src").exists())
            self.assertFalse((root / "pom.xml").exists())

    def test_phase_start_compact_archive_and_recall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self.assertIn("status: discover", (root / ".harness/state.yml").read_text())
            self.assertIn("Phase Plan: demo", (root / ".harness/phases/current/PLAN.md").read_text())

            self.assertEqual(
                self.run_cli(root, "phase", "checkpoint", "--status", "verify", "--note", "demo evidence"),
                0,
            )
            self.assertEqual(self.run_cli(root, "phase", "compact"), 0)
            self.assertIn("Status: `compact`", (root / "docs/ai-harness/STATE.md").read_text())

            self.assertEqual(self.run_cli(root, "phase", "archive"), 0)
            archives = list((root / ".harness/phases/archive").glob("*demo*"))
            self.assertEqual(len(archives), 1)
            self.assertTrue((archives[0] / "SUMMARY.md").exists())

    def test_check_reports_broken_index_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            index = root / "docs/ai-harness/INDEX.md"
            index.write_text(index.read_text(encoding="utf-8") + "\n- `missing/file.md`\n", encoding="utf-8")

            code = self.run_cli(root, "check")
            self.assertEqual(code, 1)
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertIn("missing/file.md", result["issues"][0]["message"])

    # ---- v0.2 ----

    def test_check_detects_broken_markdown_link(self) -> None:
        # B1：链接校验需覆盖 markdown `[x](path)` 链接，而不仅反引号路径。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            index = root / "docs/ai-harness/INDEX.md"
            index.write_text(
                index.read_text(encoding="utf-8") + "\n- [缺失](missing/md-link.md)\n",
                encoding="utf-8",
            )

            code = self.run_cli(root, "check")
            self.assertEqual(code, 1)
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["errors"], 1)
            self.assertIn("missing/md-link.md", result["issues"][0]["message"])

    def test_init_installs_ai_harness_skill(self) -> None:
        # C1 + v0.4：skill 唯一来源在 .agents/，--agent claude 时 .claude/ 用软链指回。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            canon = root / ".agents/skills/ai-harness/SKILL.md"
            link_dir = root / ".claude/skills/ai-harness"
            self.assertTrue(canon.exists(), "skill 真实来源应在 .agents/")
            self.assertIn("name: ai-harness", canon.read_text(encoding="utf-8"))
            self.assertTrue(link_dir.is_symlink(), ".claude 侧应为软链")
            self.assertEqual(link_dir.resolve(), (root / ".agents/skills/ai-harness").resolve())
            # 通过软链读到的内容必须与真实来源一致
            self.assertEqual(
                (link_dir / "SKILL.md").read_text(encoding="utf-8"),
                canon.read_text(encoding="utf-8"),
            )

    def test_init_without_claude_agent_skips_claude_symlink(self) -> None:
        # v0.4：仅 codex 时不应在 .claude/ 建软链，但 .agents/ 仍是真实来源。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertTrue((root / ".agents/skills/ai-harness/SKILL.md").exists())
            self.assertFalse((root / ".claude/skills/ai-harness").exists())

    def test_policies_include_engineering_baseline(self) -> None:
        # A1：母本工程智慧应作为模板一等公民进 POLICIES。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            policies = (root / "docs/ai-harness/POLICIES.md").read_text(encoding="utf-8")
            self.assertIn("工程基线", policies)
            self.assertIn("失败路径优先", policies)

    def test_plan_is_self_contained_spec(self) -> None:
        # D1：PLAN 升级为自包含 spec（涉及文件 + out-of-scope + 端到端验证）。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            plan = (root / ".harness/phases/current/PLAN.md").read_text(encoding="utf-8")
            self.assertIn("Out of Scope", plan)
            self.assertIn("端到端验证", plan)

    def test_migrate_renames_legacy_files_and_init_keeps_content(self) -> None:
        # B3：migrate 把旧命名 rename 到新结构；先 migrate 再 init 保留旧内容、无重复文件。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/ai-harness").mkdir(parents=True)
            (root / ".harness").mkdir(parents=True)
            (root / "docs/ai-harness/current-status.md").write_text("旧状态\n", encoding="utf-8")
            (root / ".harness/memory.md").write_text("旧记忆\n", encoding="utf-8")

            # dry-run 不移动
            code, out = self.run_cli_capture(root, "migrate")
            self.assertEqual(code, 0)
            self.assertIn("dry-run", out)
            self.assertTrue((root / "docs/ai-harness/current-status.md").exists())

            # --apply 执行 rename
            code, _ = self.run_cli_capture(root, "migrate", "--apply")
            self.assertEqual(code, 0)
            self.assertFalse((root / "docs/ai-harness/current-status.md").exists())
            self.assertEqual((root / "docs/ai-harness/STATE.md").read_text(encoding="utf-8"), "旧状态\n")
            self.assertFalse((root / ".harness/memory.md").exists())
            self.assertEqual((root / ".harness/memory/lessons.md").read_text(encoding="utf-8"), "旧记忆\n")

            # 迁移后 init 保留旧内容、不产生重复
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual((root / "docs/ai-harness/STATE.md").read_text(encoding="utf-8"), "旧状态\n")
            self.assertFalse((root / "docs/ai-harness/current-status.md").exists())

    def test_migrate_reports_conflict_without_overwrite(self) -> None:
        # B3：新旧并存时只报冲突，绝不自动覆盖。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/ai-harness").mkdir(parents=True)
            (root / "docs/ai-harness/current-status.md").write_text("旧\n", encoding="utf-8")
            (root / "docs/ai-harness/STATE.md").write_text("新\n", encoding="utf-8")

            code, out = self.run_cli_capture(root, "migrate", "--apply")
            self.assertEqual(code, 0)
            self.assertIn("冲突", out)
            self.assertEqual((root / "docs/ai-harness/current-status.md").read_text(encoding="utf-8"), "旧\n")
            self.assertEqual((root / "docs/ai-harness/STATE.md").read_text(encoding="utf-8"), "新\n")

    # ---- v0.3 ----

    def test_evidence_has_verify_checklist(self) -> None:
        # A2：失败路径/多视角/异常归宿点 checklist 进 EVIDENCE，只在 active phase 出现。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            evidence = (root / ".harness/phases/current/EVIDENCE.md").read_text(encoding="utf-8")
            self.assertIn("Verify Checklist", evidence)
            self.assertIn("失败路径", evidence)

    def test_compact_produces_structured_skeleton(self) -> None:
        # B2：compact 不再机械截断，生成结构化高保真骨架。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self.assertEqual(self.run_cli(root, "phase", "compact"), 0)
            handoff = (root / ".harness/phases/current/HANDOFF.md").read_text(encoding="utf-8")
            self.assertIn("改动的文件", handoff)
            self.assertIn("待填写", handoff)
            self.assertNotIn("来自 PLAN.md", handoff)  # 旧机械截断行为已移除

    def test_policies_include_subagent_mode(self) -> None:
        # C3：subagent/对抗复查协作模式进 POLICIES。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            policies = (root / "docs/ai-harness/POLICIES.md").read_text(encoding="utf-8")
            self.assertIn("协作模式", policies)
            self.assertIn("对抗式复查", policies)

    def test_roadmap_and_adr_templates_generated(self) -> None:
        # D2 + D3：项目级 ROADMAP 与 ADR 模板生成，且被 INDEX 引用。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            roadmap = root / "docs/ai-harness/ROADMAP.md"
            adr = root / "docs/adr/0000-template.md"
            self.assertTrue(roadmap.exists())
            self.assertIn("Backlog", roadmap.read_text(encoding="utf-8"))
            self.assertTrue(adr.exists())
            self.assertIn("## 约束", adr.read_text(encoding="utf-8"))
            index = (root / "docs/ai-harness/INDEX.md").read_text(encoding="utf-8")
            self.assertIn("ROADMAP.md", index)
            # INDEX 引用了 ROADMAP/ADR，check 仍 0 error
            self.assertEqual(self.run_cli(root, "check"), 0)

    def test_lessons_has_entry_schema(self) -> None:
        # D4：结构化 memory 条目 schema。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            lessons = (root / ".harness/memory/lessons.md").read_text(encoding="utf-8")
            self.assertIn("写入格式", lessons)
            self.assertIn("已确认决策", lessons)

    def test_init_without_hooks_creates_no_settings(self) -> None:
        # C2：默认不装 hook，保持可选。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertFalse((root / ".claude/settings.json").exists())

    def test_init_with_hooks_injects_stop_hook_idempotently(self) -> None:
        # C2：--with-hooks 注入 Stop hook 跑 check，且幂等不重复。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                self.run_cli(root, "init", "--profile", "core", "--agent", "codex", "--with-hooks"), 0
            )
            settings = root / ".claude/settings.json"
            self.assertTrue(settings.exists())
            data = json.loads(settings.read_text(encoding="utf-8"))
            commands = [h["command"] for entry in data["hooks"]["Stop"] for h in entry["hooks"]]
            self.assertTrue(any("harness" in c and "check" in c for c in commands))

            before = settings.read_text(encoding="utf-8")
            self.assertFalse(harness.write_stop_hook(root))  # 再注入应幂等
            self.assertEqual(settings.read_text(encoding="utf-8"), before)

    def test_with_hooks_preserves_existing_settings(self) -> None:
        # C2：已有 settings.json 时 JSON merge 保留原内容。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir(parents=True)
            (root / ".claude/settings.json").write_text(
                '{"model": "opus", "hooks": {"Stop": []}}', encoding="utf-8"
            )
            self.assertEqual(
                self.run_cli(root, "init", "--profile", "core", "--agent", "codex", "--with-hooks"), 0
            )
            data = json.loads((root / ".claude/settings.json").read_text(encoding="utf-8"))
            self.assertEqual(data["model"], "opus")
            commands = [h["command"] for entry in data["hooks"]["Stop"] for h in entry["hooks"]]
            self.assertTrue(any("harness" in c and "check" in c for c in commands))

    def test_upgrade_backfills_missing_and_bumps_version(self) -> None:
        # B4：旧库 upgrade 补齐缺失文件并 bump schemaVersion；dry-run 不动。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            # 模拟旧版本库：降级 schemaVersion、删除 v0.3 才有的文件
            state_path = root / ".harness/state.yml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace("schemaVersion: 2", "schemaVersion: 1"),
                encoding="utf-8",
            )
            (root / "docs/ai-harness/ROADMAP.md").unlink()
            (root / "docs/adr/0000-template.md").unlink()

            code, out = self.run_cli_capture(root, "upgrade")
            self.assertEqual(code, 0)
            self.assertIn("dry-run", out)
            self.assertFalse((root / "docs/ai-harness/ROADMAP.md").exists())

            code, _ = self.run_cli_capture(root, "upgrade", "--apply")
            self.assertEqual(code, 0)
            self.assertTrue((root / "docs/ai-harness/ROADMAP.md").exists())
            self.assertTrue((root / "docs/adr/0000-template.md").exists())
            self.assertIn("schemaVersion: 2", state_path.read_text(encoding="utf-8"))

    def test_upgrade_refresh_infra_updates_template_files(self) -> None:
        # B4 + v0.4：--refresh-infra 刷新真实来源（.agents/），软链自动跟随。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            canon = root / ".agents/skills/ai-harness/SKILL.md"
            link = root / ".claude/skills/ai-harness/SKILL.md"
            canon.write_text("# 旧 skill 内容\n", encoding="utf-8")
            self.assertEqual(link.read_text(encoding="utf-8"), "# 旧 skill 内容\n")  # 软链同步可见

            self.assertEqual(self.run_cli(root, "upgrade", "--apply", "--refresh-infra"), 0)
            self.assertIn("name: ai-harness", canon.read_text(encoding="utf-8"))
            self.assertEqual(link.read_text(encoding="utf-8"), canon.read_text(encoding="utf-8"))

    # ---- v0.4：.agents 唯一来源 + Claude 软链 ----

    def test_init_is_idempotent_on_symlink(self) -> None:
        # 连跑两次 init：第二次不应再次报告 skill 软链为变更。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            link_dir = root / ".claude/skills/ai-harness"
            self.assertTrue(link_dir.is_symlink())

            code, out = self.run_cli_capture(root, "init", "--profile", "core", "--agent", "claude")
            self.assertEqual(code, 0)
            self.assertNotIn(".claude/skills/ai-harness (symlink", out)
            self.assertTrue(link_dir.is_symlink())

    def test_symlink_falls_back_to_copy_when_unavailable(self) -> None:
        # 软链不可用（Windows 未开开发者模式等）回退为普通副本，check 报 warning。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = harness.os.symlink

            def boom(*_a, **_kw):
                raise OSError("symlink not supported")

            harness.os.symlink = boom
            try:
                self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            finally:
                harness.os.symlink = original

            link_dir = root / ".claude/skills/ai-harness"
            self.assertTrue(link_dir.exists())
            self.assertFalse(link_dir.is_symlink(), "应回退为普通副本")
            self.assertTrue((link_dir / "SKILL.md").exists())

            self.run_cli(root, "check")
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            messages = [i["message"] for i in result["issues"]]
            self.assertTrue(any("退化为副本" in m for m in messages), messages)

    def test_check_reports_broken_skill_symlink(self) -> None:
        # 软链断裂（真实来源被删）-> check 报 error。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            shutil_mod = harness.shutil
            shutil_mod.rmtree(root / ".agents/skills/ai-harness")

            code = self.run_cli(root, "check")
            self.assertEqual(code, 1)
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            errors = [i for i in result["issues"] if i["level"] == "error"]
            self.assertTrue(any("软链断裂" in i["message"] for i in errors), result["issues"])

    def test_migrate_collapses_legacy_claude_skill_to_symlink(self) -> None:
        # 遗留布局：.claude/skills/ai-harness 是真实目录 -> migrate 改软链 + 真实来源迁到 .agents/。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / ".claude/skills/ai-harness"
            legacy.mkdir(parents=True)
            (legacy / "SKILL.md").write_text("# legacy\n", encoding="utf-8")

            # dry-run 不动
            code, out = self.run_cli_capture(root, "migrate")
            self.assertEqual(code, 0)
            self.assertIn("dry-run", out)
            self.assertFalse(legacy.is_symlink())
            self.assertFalse((root / ".agents/skills/ai-harness/SKILL.md").exists())

            # --apply 收敛
            self.assertEqual(self.run_cli(root, "migrate", "--apply"), 0)
            self.assertTrue(legacy.is_symlink())
            self.assertEqual(
                (root / ".agents/skills/ai-harness/SKILL.md").read_text(encoding="utf-8"),
                "# legacy\n",
            )
            self.assertEqual((legacy / "SKILL.md").read_text(encoding="utf-8"), "# legacy\n")

    # ---- v0.5 D6：收敛 current/ 文件冗余 ----

    def test_checkpoint_does_not_pollute_handoff(self) -> None:
        # D6：checkpoint 只写 EVIDENCE + PROGRESS；HANDOFF 留给 compact 写。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            handoff = root / ".harness/phases/current/HANDOFF.md"
            before = handoff.read_text(encoding="utf-8")

            self.assertEqual(
                self.run_cli(root, "phase", "checkpoint", "--status", "execute", "--note", "step1"),
                0,
            )
            after = handoff.read_text(encoding="utf-8")
            self.assertEqual(before, after, "checkpoint 不应改 HANDOFF")
            self.assertNotIn("Checkpoint", after)

            # EVIDENCE 与 PROGRESS 必须被 checkpoint 触达
            evidence = (root / ".harness/phases/current/EVIDENCE.md").read_text(encoding="utf-8")
            progress = (root / ".harness/phases/current/PROGRESS.yml").read_text(encoding="utf-8")
            self.assertIn("step1", evidence)
            self.assertIn("step1", progress)

            # compact 才写 HANDOFF
            self.assertEqual(self.run_cli(root, "phase", "compact"), 0)
            self.assertIn("待填写", handoff.read_text(encoding="utf-8"))

    # ---- v0.5 B5：补测试覆盖 ----

    def test_init_is_globally_idempotent(self) -> None:
        # B5：init 两次产出文件指纹应完全一致（不算 .harness/checks/latest.json 每次必变）。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex,claude"), 0)
            snapshot1 = self._fingerprint(root)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex,claude"), 0)
            snapshot2 = self._fingerprint(root)
            self.assertEqual(snapshot1, snapshot2)

    def test_upgrade_is_idempotent_on_clean_install(self) -> None:
        # B5：装好后再 upgrade --apply 不应有任何刷新/新增。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            code, out = self.run_cli_capture(root, "upgrade", "--apply")
            self.assertEqual(code, 0)
            self.assertIn("harness 已是最新", out)
            self.assertNotIn("新增：", out)
            self.assertNotIn("刷新：", out)

    def test_check_layering_warns_on_machine_state_in_docs(self) -> None:
        # B5：check_layering 分支——docs/ 下文件含 machine-state 字段应 warning。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            (root / "docs/ai-harness/STATE.md").write_text(
                "# state\n\nschemaVersion: 99\nstartedAt: now\n",
                encoding="utf-8",
            )
            self.run_cli(root, "check")
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            messages = [i["message"] for i in result["issues"]]
            self.assertTrue(any("machine-state" in m for m in messages), messages)

    def test_migrate_reports_advisory_for_legacy_docs(self) -> None:
        # B5：migrate advisory 分支——遗留 engineering-guidelines.md 应给出手工迁移提示。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/ai-harness").mkdir(parents=True)
            (root / "docs/ai-harness/engineering-guidelines.md").write_text("old\n", encoding="utf-8")
            code, out = self.run_cli_capture(root, "migrate")
            self.assertEqual(code, 0)
            self.assertIn("建议手工迁移", out)
            self.assertIn("engineering-guidelines.md", out)

    # ---- v0.5 B6：memory 生命周期 ----

    def test_check_warns_on_oversized_lessons(self) -> None:
        # B6：lessons.md 超过 limits.lessonsMaxLines 阈值时 check 报 warning。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            lessons = root / ".harness/memory/lessons.md"
            lessons.write_text("# Lessons\n\n" + "- noise\n" * 250, encoding="utf-8")

            self.run_cli(root, "check")
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            messages = [i["message"] for i in result["issues"]]
            self.assertTrue(any("lessons.md 超过" in m for m in messages), messages)
            self.assertEqual(result["summary"]["errors"], 0)  # warning 不阻塞

    # ---- v0.5 D5：OUT-OF-SCOPE.md 一等产物 ----

    def test_init_generates_out_of_scope_and_index_references_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            oos = root / "docs/ai-harness/OUT-OF-SCOPE.md"
            self.assertTrue(oos.exists())
            self.assertIn("重审条件", oos.read_text(encoding="utf-8"))
            index = (root / "docs/ai-harness/INDEX.md").read_text(encoding="utf-8")
            self.assertIn("OUT-OF-SCOPE.md", index)
            # check 仍 0 error（INDEX 引用真实文件）
            self.assertEqual(self.run_cli(root, "check"), 0)

    # ---- v0.5 C4：可选 slash commands ----

    def test_init_without_commands_creates_no_command_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            self.assertFalse((root / ".claude/commands").exists())

    def test_init_with_commands_generates_idempotent_templates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                self.run_cli(root, "init", "--profile", "core", "--agent", "claude", "--with-commands"), 0
            )
            commands = sorted((root / ".claude/commands").glob("harness-*.md"))
            self.assertGreaterEqual(len(commands), 3)
            for cmd in commands:
                text = cmd.read_text(encoding="utf-8")
                self.assertTrue(text.startswith("---\n"))
                self.assertIn("description:", text)

            # 再跑一次 init --with-commands 应幂等：内容字节级一致
            before = {c: c.read_text(encoding="utf-8") for c in commands}
            self.assertEqual(
                self.run_cli(root, "init", "--profile", "core", "--agent", "claude", "--with-commands"), 0
            )
            for c, body in before.items():
                self.assertEqual(c.read_text(encoding="utf-8"), body)

    # ---- v0.6：Codex/AGENTS.md 单文件引用 skill ----

    def test_agents_router_references_canonical_skill(self) -> None:
        # v0.6：AGENTS.md/CLAUDE.md ROUTER 必须单文件引用 .agents/skills/ai-harness/SKILL.md。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex,claude"), 0)
            for entry in ("AGENTS.md", "CLAUDE.md"):
                text = (root / entry).read_text(encoding="utf-8")
                self.assertIn(".agents/skills/ai-harness/SKILL.md", text,
                              f"{entry} 应在 ROUTER 内引用 skill 唯一来源")
                # 不应展开 skill 正文（避免启动加载量膨胀）
                self.assertNotIn("Phase 生命周期", text)

    # ---- v0.7：fresh checkout / CI 卫生 ----

    def test_check_tolerates_fresh_checkout(self) -> None:
        # CI / fresh clone：latest.json 被 gitignore 不存在、archive 空目录靠 .gitkeep 保留 → check 仍 0 error。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            # .gitkeep 让空 archive 目录可被 git 跟踪
            self.assertTrue((root / ".harness/phases/archive/.gitkeep").exists())
            # 模拟 fresh clone：运行时产物 latest.json 未被提交、不存在
            (root / ".harness/checks/latest.json").unlink()
            self.assertEqual(self.run_cli(root, "check"), 0)  # 不再因 latest.json/archive 报 error
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            self.assertEqual(result["summary"]["errors"], 0)

    # ---- v0.8：Cursor 原生扫 .agents/skills/（无需 .cursor/skills/ 副本）----

    def test_init_agents_skill_is_canonical_for_all_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            self.assertTrue((root / ".agents/skills/ai-harness/SKILL.md").exists())
            self.assertFalse((root / ".cursor").exists())

    def test_check_warns_legacy_cursor_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            legacy = root / ".cursor/skills/ai-harness"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root / ".agents/skills/ai-harness", legacy)
            self.run_cli(root, "check")
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            messages = [i["message"] for i in result["issues"]]
            self.assertTrue(any("遗留 v0.8" in m for m in messages), messages)

    def test_migrate_removes_legacy_cursor_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "claude"), 0)
            legacy = root / ".cursor/skills/ai-harness"
            legacy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(root / ".agents/skills/ai-harness", legacy)
            self.assertEqual(self.run_cli(root, "migrate", "--apply"), 0)
            self.assertFalse(legacy.exists())
            self.assertEqual(self.run_cli(root, "check"), 0)

    # ---- v0.9 修地基（N1/N2/N3/N4） ----

    def test_update_state_preserves_user_limits_and_context(self) -> None:
        # N1：phase 操作不得静默丢失用户对 limits/requiredRead 的定制。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            state_path = root / ".harness/state.yml"
            text = state_path.read_text(encoding="utf-8")
            text = text.replace("stateMaxLines: 150", "stateMaxLines: 999")
            text = text.replace(
                "    - docs/ai-harness/DECISIONS.md",
                "    - docs/ai-harness/DECISIONS.md\n    - docs/ai-harness/GLOSSARY.md",
            )
            state_path.write_text(text, encoding="utf-8")

            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            after = state_path.read_text(encoding="utf-8")
            self.assertIn("stateMaxLines: 999", after)          # 用户阈值保真
            self.assertIn("GLOSSARY.md", after)                 # 用户必读项保真
            self.assertIn("status: discover", after)            # 定点字段确实更新

    def test_started_at_stable_across_checkpoints(self) -> None:
        # N1 同源：startedAt 是"开始时间"，checkpoint 不得把它刷成当前时间。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            started = harness.parse_state(root / ".harness/state.yml").get("phase.startedAt")
            self.assertTrue(started)

            self.assertEqual(self.run_cli(root, "phase", "checkpoint", "--status", "verify"), 0)
            self.assertEqual(
                harness.parse_state(root / ".harness/state.yml").get("phase.startedAt"),
                started,
            )
            # archive 回 idle 时清零
            self.assertEqual(self.run_cli(root, "phase", "archive"), 0)
            self.assertEqual(harness.parse_state(root / ".harness/state.yml").get("phase.startedAt"), "")

    def test_check_warns_on_schema_version_mismatch(self) -> None:
        # N2：state.schemaVersion 落后 → warning（兑现 README §5），非 error。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            state_path = root / ".harness/state.yml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace(
                    f"schemaVersion: {harness.SCHEMA_VERSION}", "schemaVersion: 1", 1
                ),
                encoding="utf-8",
            )
            code = self.run_cli(root, "check")
            self.assertEqual(code, 0)  # warning 不拦 CI
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            messages = [i["message"] for i in result["issues"]]
            self.assertTrue(any("schemaVersion" in m and "upgrade" in m for m in messages))

    def test_upgrade_bump_clears_schema_mismatch_warning(self) -> None:
        # N2 闭环：upgrade 后 mismatch warning 消失，且 state 内容仍保真。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            state_path = root / ".harness/state.yml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace(
                    f"schemaVersion: {harness.SCHEMA_VERSION}", "schemaVersion: 1", 1
                ),
                encoding="utf-8",
            )
            self.assertEqual(self.run_cli(root, "upgrade", "--apply"), 0)
            self.assertIn(f"schemaVersion: {harness.SCHEMA_VERSION}", state_path.read_text(encoding="utf-8"))
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            # 上一次 check 已被 upgrade 后重跑覆盖前，需主动再 check
            self.assertEqual(self.run_cli(root, "check"), 0)
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            self.assertFalse(any("schemaVersion" in i["message"] for i in result["issues"]))

    def test_check_tolerates_non_numeric_limit(self) -> None:
        # N3：limits 阈值非数字 → 不崩溃，回退默认 + warning（fail-closed）。
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            state_path = root / ".harness/state.yml"
            state_path.write_text(
                state_path.read_text(encoding="utf-8").replace("stateMaxLines: 150", "stateMaxLines: abc"),
                encoding="utf-8",
            )
            code = self.run_cli(root, "check")  # 旧行为：ValueError 崩溃
            self.assertEqual(code, 0)
            result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
            self.assertTrue(any("非整数" in i["message"] for i in result["issues"]))

    def test_version_flag_reports_single_source(self) -> None:
        # N4：--version 打印 __version__，且与该常量一致。
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            with self.assertRaises(SystemExit) as ctx:
                harness.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn(harness.__version__, buffer.getvalue())

    # ---- G5 深化 check（stale phase + required sections） ----

    def _check_messages(self, root: Path) -> list[str]:
        self.run_cli(root, "check")
        result = json.loads((root / ".harness/checks/latest.json").read_text(encoding="utf-8"))
        return [i["message"] for i in result["issues"]]

    def _set_started_days_ago(self, root: Path, days: int) -> None:
        ts = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
        p = root / ".harness/state.yml"
        p.write_text(re.sub(r'startedAt: ".*"', f'startedAt: "{ts}"', p.read_text(encoding="utf-8")), encoding="utf-8")

    def _fill_plan(self, root: Path) -> None:
        # 写一份不含模板占位、含必备 heading 的 PLAN，避免空壳/heading 检查干扰 stale 测试
        (root / ".harness/phases/current/PLAN.md").write_text(
            "# Phase Plan: x\n\n## Goal\n\n真实目标一句话。\n\n## Acceptance Criteria\n\n- 有 handoff。\n",
            encoding="utf-8",
        )

    def test_check_warns_on_stale_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self._fill_plan(root)
            self._set_started_days_ago(root, 10)
            msgs = self._check_messages(root)
            self.assertTrue(any("无 checkpoint" in m for m in msgs))
            self.assertEqual(self.run_cli(root, "check"), 0)  # 仅 warning，不拦

    def test_recent_checkpoint_clears_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self._fill_plan(root)
            self._set_started_days_ago(root, 10)
            # 一次新 checkpoint → PROGRESS.yml 有新 at → 参考时间刷新，stale 消失（startedAt 仍旧，由 N1 保真）
            self.assertEqual(self.run_cli(root, "phase", "checkpoint", "--status", "execute"), 0)
            self.assertFalse(any("无 checkpoint" in m for m in self._check_messages(root)))

    def test_stale_fail_soft_on_bad_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self._fill_plan(root)
            p = root / ".harness/state.yml"
            p.write_text(re.sub(r'startedAt: ".*"', 'startedAt: "not-a-date"', p.read_text(encoding="utf-8")), encoding="utf-8")
            self.assertEqual(self.run_cli(root, "check"), 0)  # 不崩
            self.assertFalse(any("无 checkpoint" in m for m in self._check_messages(root)))

    def test_non_numeric_stale_days_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            self._fill_plan(root)
            self._set_started_days_ago(root, 10)
            p = root / ".harness/state.yml"
            p.write_text(
                p.read_text(encoding="utf-8").replace("lessonsMaxLines: 200", "lessonsMaxLines: 200\n  stalePhaseDays: xyz"),
                encoding="utf-8",
            )
            msgs = self._check_messages(root)
            self.assertTrue(any("stalePhaseDays 非整数" in m for m in msgs))  # 容错 warning
            self.assertTrue(any("无 checkpoint" in m for m in msgs))          # 回退默认 7 后仍判 stale

    def test_fresh_phase_plan_shell_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            # 刚 start、PLAN 还是模板 → 空壳 warning
            self.assertTrue(any("空壳" in m for m in self._check_messages(root)))
            self._fill_plan(root)
            self.assertFalse(any("空壳" in m for m in self._check_messages(root)))

    def test_required_section_missing_heading_warns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            plan = root / ".harness/phases/current/PLAN.md"
            plan.write_text(plan.read_text(encoding="utf-8").replace("## Acceptance Criteria", "## 验收"), encoding="utf-8")
            self.assertTrue(any("缺少必备 section" in m and "Acceptance Criteria" in m for m in self._check_messages(root)))

    def test_idle_phase_skips_stale_and_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            # idle：current/ PLAN 是模板含占位，但 status idle → 不查 stale/required
            msgs = self._check_messages(root)
            self.assertFalse(any("空壳" in m or "无 checkpoint" in m for m in msgs))

    def test_required_section_placeholders_match_templates(self) -> None:
        # 防漂移：REQUIRED_SECTIONS 里的占位串必须真出现在模板输出中；heading 亦然。
        plan = harness.current_plan("x")
        for ph in harness.REQUIRED_SECTIONS[".harness/phases/current/PLAN.md"]["placeholders"]:
            self.assertIn(ph, plan)
        for h in harness.REQUIRED_SECTIONS[".harness/phases/current/PLAN.md"]["headings"]:
            self.assertIn(h, plan)
        evidence = harness.evidence_doc("x")
        for h in harness.REQUIRED_SECTIONS[".harness/phases/current/EVIDENCE.md"]["headings"]:
            self.assertIn(h, evidence)

    # ---- G1 phase↔branch（选项 1，opt-in --branch） ----

    @staticmethod
    def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(root), capture_output=True, text=True,
        )

    def _init_git(self, root: Path) -> None:
        self._git(root, "init", "-q")
        self._git(root, "commit", "--allow-empty", "-q", "-m", "init")

    def test_phase_start_branch_creates_and_switches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_git(root)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            code, out = self.run_cli_capture(root, "phase", "start", "demo", "--branch")
            self.assertEqual(code, 0)
            self.assertEqual(harness.current_git_branch(root), "phase/demo")
            self.assertIn("phase/demo", out)

    def test_phase_start_branch_switches_to_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_git(root)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self._git(root, "checkout", "-q", "-b", "phase/demo")   # 预先建好
            self._git(root, "checkout", "-q", "-")                  # 切回原分支
            self.assertNotEqual(harness.current_git_branch(root), "phase/demo")
            self.assertEqual(self.run_cli(root, "phase", "start", "demo", "--branch"), 0)
            self.assertEqual(harness.current_git_branch(root), "phase/demo")

    def test_phase_start_branch_fail_soft_when_not_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)  # 非 git repo
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            code, out = self.run_cli_capture(root, "phase", "start", "demo", "--branch")
            self.assertEqual(code, 0)  # 不崩，phase 照常
            self.assertIn("非 git 仓库", out)
            self.assertEqual(harness.parse_state(root / ".harness/state.yml").get("phase.status"), "discover")

    def test_phase_start_without_branch_leaves_git_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_git(root)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            before = harness.current_git_branch(root)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)  # 无 --branch
            self.assertEqual(harness.current_git_branch(root), before)  # 分支零变化

    def test_archive_hints_when_on_phase_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._init_git(root)
            self.assertEqual(self.run_cli(root, "init", "--profile", "core", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo", "--branch"), 0)
            code, out = self.run_cli_capture(root, "phase", "archive")
            self.assertEqual(code, 0)
            self.assertIn("phase 分支", out)

    # ---- bootstrap（已有仓库首次上下文初始化） ----

    def test_bootstrap_starts_context_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            code, out = self.run_cli_capture(root, "bootstrap")
            self.assertEqual(code, 0)
            state = harness.parse_state(root / ".harness/state.yml")
            self.assertEqual(state.get("phase.status"), "discover")
            self.assertEqual(state.get("phase.slug"), "bootstrap-context")
            plan = (root / ".harness/phases/current/PLAN.md").read_text(encoding="utf-8")
            self.assertIn("bootstrap-context", plan)
            self.assertIn("对称写进两边 CONTEXT", plan)  # 跨仓经验入模板

    def test_bootstrap_auto_inits_and_suggests_java(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pom.xml").write_text("<project/>", encoding="utf-8")  # Java 线索
            self.assertFalse((root / ".harness/state.yml").exists())
            code, out = self.run_cli_capture(root, "bootstrap")  # 未 init → 自动 init
            self.assertEqual(code, 0)
            self.assertTrue((root / ".harness/state.yml").exists())
            self.assertIn("pom.xml", out)
            self.assertIn("java-spring", out)  # Java 栈 profile 建议

    def test_bootstrap_refuses_when_phase_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            with self.assertRaises(SystemExit):
                self.run_cli(root, "bootstrap")  # 已有 active phase → 拒绝

    def test_check_nudges_when_context_is_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            # 刚 init，CONTEXT 是模板 → nudge
            self.assertTrue(any("CONTEXT 仍是模板" in m for m in self._check_messages(root)))
            # 填充后 nudge 消失
            (root / "docs/ai-harness/CONTEXT.md").write_text(
                "# 项目上下文\n\n## 项目\n\n- 真实定位。\n\n## 架构地图\n\n- 真实架构。\n", encoding="utf-8")
            self.assertFalse(any("CONTEXT 仍是模板" in m for m in self._check_messages(root)))

    def test_context_placeholders_match_template(self) -> None:
        # 防漂移：nudge 用的占位串必须真出现在 context_doc 模板里。
        ctx = harness.context_doc("x")
        for ph in harness.CONTEXT_PLACEHOLDERS:
            self.assertIn(ph, ctx)

    # ---- STATE 有界（方向2：进度归 ROADMAP，archive 重置无损） ----

    def test_state_doc_points_progress_to_roadmap(self) -> None:
        doc = harness.state_doc("x")
        self.assertIn("ROADMAP", doc)
        self.assertIn("phase archive", doc)  # 提示本文会被重置

    def test_archive_prints_state_reset_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            code, out = self.run_cli_capture(root, "phase", "archive")
            self.assertEqual(code, 0)
            self.assertIn("ROADMAP", out)  # 安全提示引导进度归 ROADMAP

    def test_state_bounded_policy_present(self) -> None:
        self.assertIn("STATE.md`", harness.policies_doc("core"))
        self.assertIn("跨版本进度记", harness.policies_doc("core"))

    # ---- 工作流增强：task / next / skill 完整循环 ----

    def test_task_starts_phase_with_goal_prefilled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            code, out = self.run_cli_capture(root, "task", "Fix Login Bug")
            self.assertEqual(code, 0)
            state = harness.parse_state(root / ".harness/state.yml")
            self.assertEqual(state.get("phase.status"), "discover")
            self.assertEqual(state.get("phase.slug"), "fix-login-bug")  # 从 goal 派生
            plan = (root / ".harness/phases/current/PLAN.md").read_text(encoding="utf-8")
            self.assertIn("Fix Login Bug", plan)              # Goal 预填
            self.assertNotIn("做完什么算完成", plan)          # 占位被替换

    def test_task_chinese_goal_falls_back_to_task_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "task", "修复登录问题"), 0)
            state = harness.parse_state(root / ".harness/state.yml")
            self.assertEqual(state.get("phase.slug"), "task")  # 纯中文 → 兜底
            self.assertIn("修复登录问题", (root / ".harness/phases/current/PLAN.md").read_text(encoding="utf-8"))

    def test_task_refuses_when_phase_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            self.assertEqual(self.run_cli(root, "phase", "start", "demo"), 0)
            with self.assertRaises(SystemExit):
                self.run_cli(root, "task", "另一个任务")

    def test_next_guides_by_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "codex"), 0)
            # idle + CONTEXT 模板 → 指向 bootstrap
            _, out1 = self.run_cli_capture(root, "next")
            self.assertIn("bootstrap", out1)
            # 填了 CONTEXT → 指向 task
            (root / "docs/ai-harness/CONTEXT.md").write_text("# 项目上下文\n\n真实内容。\n", encoding="utf-8")
            _, out2 = self.run_cli_capture(root, "next")
            self.assertIn("harness task", out2)
            # 活动态 → 指向 checkpoint
            self.assertEqual(self.run_cli(root, "task", "do x"), 0)
            _, out3 = self.run_cli_capture(root, "next")
            self.assertIn("checkpoint", out3)

    def test_skill_doc_encodes_full_loop(self) -> None:
        doc = harness.skill_doc()
        for cmd in ("harness init", "harness bootstrap", "harness task", "harness next"):
            self.assertIn(cmd, doc)

    def test_with_commands_includes_task_slash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.run_cli(root, "init", "--agent", "claude", "--with-commands"), 0)
            task_cmd = root / ".claude/commands/harness-task.md"
            self.assertTrue(task_cmd.exists())
            text = task_cmd.read_text(encoding="utf-8")
            self.assertIn("$ARGUMENTS", text)       # 接受用户任务描述
            self.assertIn("harness task", text)

    @staticmethod
    def _fingerprint(root: Path) -> dict:
        skip = {".harness/checks/latest.json"}
        out: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = str(path.relative_to(root))
            if rel in skip:
                continue
            out[rel] = path.read_text(encoding="utf-8", errors="replace")
        return out


if __name__ == "__main__":
    unittest.main()
