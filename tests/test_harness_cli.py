from __future__ import annotations

import contextlib
import importlib.machinery
import io
import json
import shutil
import tempfile
import unittest
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
