#!/usr/bin/env bash
# 合并 PR 且规避 `gh pr merge --delete-branch` 反复触发的本地 ref 竞态
# （"cannot lock ref refs/remotes/origin/main"）。
#
# 根因：--delete-branch 让 gh 在合并后于本地 checkout main + 删分支 + fetch，
# 与其内部 fetch 抢更新 origin/main 的 ref。这里改为：只在 GitHub 侧合并，
# 本地用一次确定性的 fetch + ff 兜住，最后再显式删分支。
#
# 用法: scripts/merge-pr.sh <pr-number> [head-branch]
#   head-branch 省略时取当前分支（在切到 main 之前捕获）。
set -euo pipefail

pr="${1:?用法: scripts/merge-pr.sh <pr-number> [head-branch]}"
head_branch="${2:-$(git rev-parse --abbrev-ref HEAD)}"

if [ "$head_branch" = "main" ]; then
  echo "拒绝：head-branch 不能是 main" >&2
  exit 1
fi

# 1) 只在 GitHub 侧 rebase 合并（不加 --delete-branch，避免本地 ref 竞态）
gh pr merge "$pr" --rebase --admin

# 2) 本地确定性同步（幂等；即使 gh 内部 fetch 抖动也能收敛）
git switch main 2>/dev/null || git checkout main
git fetch origin
git merge --ff-only origin/main

# 3) 清理分支（远程 + 本地）。main 的 ruleset 只约束 main，feature 分支可删。
git push origin --delete "$head_branch" 2>/dev/null || true
git branch -D "$head_branch" 2>/dev/null || true

echo "✓ merged PR #$pr → main @ $(git rev-parse --short HEAD)"
