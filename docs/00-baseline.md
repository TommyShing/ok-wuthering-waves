# 00 · 基线（Baseline）

## 这份仓库是什么

`data/apps/ok-ww/working/` 的**本地独立 Git 仓库**，只跟踪**源码**。

- 不是 `data/apps/ok-ww/repo/` —— 那是 CNB 更新镜像（`cnb.cool/ok-oldking/ok-ww-update2.git`），
  19 个压缩提交、detached HEAD、历史与 GitHub 不一致。改它会被下次自动更新冲掉。
- 本仓库的目的：**在 ok-ww 自动更新把 `working/` 覆盖掉之后，仍能取回我们的改动。**

## 基线信息

| 项 | 值 |
|---|---|
| ok-ww 版本 | v3.7.4（`data/apps/ok-ww/app.json` → `current_version`） |
| 上游 tag | `v3.7.4` |
| 上游 commit（GitHub） | `36d5639` |
| 上游 commit（本地 CNB 镜像） | `36d56391019170887c7560cfbad16a159c395682` |
| 本仓库基线 commit | `9b412024d0756ece3340d9a578195f74c2c8b13a` |
| 基线分支 | `main` |
| 工作分支 | `feat/book-target-runtime` |
| 跟踪文件数 | 407 |
| 仓库体积 | 约 8.5 MB（源码 + i18n + icons + 根目录文件） |

## 跟踪 / 排除范围

**跟踪**（`.gitignore` 之外的）：
```
src/          1.62 MB   ← 业务逻辑，我们的改动都在这里
ok/           6.27 MB   ← 框架层
pyappify/     0.08 MB
i18n/         0.34 MB
icons/        0.17 MB
readme/
config.py  main.py  main_debug.py  pyappify.yml  requirements.txt  README.md  .gitignore
```

**排除**（`.gitignore` 中）：
```
screenshots/  110.67 MB  运行时截图
cache/         20.64 MB  openvino 缓存
assets/        39.70 MB  模板图集 + onnx 模型
configs/        0.05 MB  个人配置（含账号相关）
logs/           7.16 MB  运行日志
__pycache__/  *.pyc
```

排除理由：与本次改动无关，体积大，且 `configs/` 属个人数据。

## 如何回退

```bash
cd data/apps/ok-ww/working

git status                              # 先看当前状态
git checkout main                       # 回到 v3.7.4 原始基线
git checkout v0.3-runtime-table         # 回到某个中间版本
git checkout -f main                    # 强制丢弃工作区改动，彻底还原
```

## 如何在新版 ok-ww 上恢复我们的改动

1. ok-ww 自动更新后，`working/` 被覆盖为新版本。
2. 进入 `working/`，确认 `.git` 还在（更新一般不动 `.git`）。
   - 若 `.git` 也丢了，从 GitHub fork 重新 clone，或从 `docs/` 重建。
3. `git status` 会显示大量源码被改动（那是新版本 vs 旧版本）。
4. `git stash` 或新建分支保存新版本 → 再用 `git cherry-pick` / `git rebase` 把我们的提交搬到新基线。

**建议**：更新前先 `git -C working tag pre-update-<版本>`，更新后好对比。

## 关键约束

- **最小改动**：这是个大型项目，我们不是深度参与者。改动只限必要范围。
- **不碰**：滑动机制、`boss_proceed` 模板、点击后所有流程、死亡恢复链路。
- **保留**：特异梦魇的 `+5` 序号偏移（前 5 项是巢穴不是 4C，这是语义不是几何）。
