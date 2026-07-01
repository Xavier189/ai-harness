# Evidence: g5-deepen-check

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests   → Ran 54 tests OK（46 + 8 新增 G5）
$ python3 evals/run.py                     → 5/5 场景通过
$ python3 ai_harness.py check              → check: 0 error(s), 0 warning(s)
```

- **check_stale_phase**：测试覆盖 命中(startedAt 10 天前)/未命中(新 checkpoint 刷新参考时间,含 N1 保真验证)/时间解析失败 fail-soft 不崩/非数字 stalePhaseDays 回退默认 7 + warning。
- **check_required_sections**：刚 start 的 PLAN 模板 → 空壳 warning；填好 → 消失；删 heading → "缺少必备 section" warning；idle 态不查。
- **防漂移**：`test_required_section_placeholders_match_templates` 断言占位串/heading 真出现在 `current_plan()`/`evidence_doc()` 输出——改模板会让该测试红。

### 踩坑记录

占位符最初用裸子串 `用一句话写清楚` → 本 phase 的 PLAN 正文**在描述占位符检测**时提到该串,check 误报自己空壳。改用模板独有高区分度尾串（`做完什么算完成` / `路径具体到可被 subagent 直接定位`）消除。教训:空壳检测的占位符要选"只可能出现在未填模板里"的片段。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：stale 时间解析失败 fail-soft 跳过；非数字阈值回退默认；全 warning 不拦 CI。
- [x] 多视角已过：运维（check 提示"该 checkpoint/compact"与"phase 空壳"）；安全（无 secret/payload）。
- [x] 异常归宿点：`_parse_ts` 吞 ValueError/TypeError 返回 None，不抛栈。
- [x] 对外契约变更已告知下游：新增两条 warning 级 check，不改退出码语义（error 才返回 1）。
- [x] 端到端验证有真实输出，非"看起来好了"（见上）。

## Checkpoint 2026-07-01T03:04:38+00:00

- Status: `verify`
- Note: G5 落地：check_stale_phase + check_required_sections；54 tests OK(+8) / evals 5/5 / check 0e0w；踩坑=占位符裸子串匹配会命中讨论占位符的 PLAN 自身，改用高区分度尾串
