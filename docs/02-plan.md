# 02 · 计划（Plan）

目标：**去掉写死的分组表，改成运行时动态建表**，让「从上往下第 N 个」不再依赖版本更新。

## 设计原则

1. **最小改动**：只碰 `click_on_book_target` 一个函数 + `FarmEchoTask` 的几个常量。
2. **保留交互**：仍然是"填第 N 个"（作者已定的功能延续性，不改交互）。
3. **保留滑动机制**：点轨道滚动，不动（用户要求能用就不动）。
4. **不识别地区标题**：标题没有 `boss_proceed` 按钮，天然不计数。
5. **不用滑块长度反推总高**：本次不做，留待后续。
6. **每步可独立回退**：每个阶段一个 commit + 一个 tag + 一份 md。

## 核心思路

```
旧：人提前告诉程序"列表长什么样"（structure / total）
新：程序自己扫一遍，把"第几行 ↔ 滚到哪"量出来
```

因为按钮 y 间距是**当场可测**的（相邻两个按钮 y 一减就是行高），
所以行高、行数、当前滚到哪，全部可以运行时得到，无需任何写死常量。

## 阶段划分

### 阶段 0 · 建仓（tag `v0.1-audit`）
**代码改动：无。**

- [x] `git init working/`，`.gitignore` 排除 screenshots/cache/assets/configs/logs
- [x] `main` = v3.7.4 基线（`9b41202`）
- [x] 分支 `feat/book-target-runtime`
- [x] `docs/00-baseline.md`、`01-audit.md`、`02-plan.md`

### 阶段 1 · 去写死（tag `v0.2-remove-hardcoded`）
**只做减法。中间态允许"≥5 明确报错"，比现在"刷错"好。**

- [ ] `click_on_book_target`：删 `container_max_rows` 分叉、删 `header_h`、删 `0.55`、删 `0.73`
- [ ] 暂时降级为"只支持首屏 N≤4"，≥5 抛明确异常
- [ ] `FarmEchoTask`：删 `total_weekly_number`、`total_boss_number`
- [ ] **保留** `nightmare_structure`（`+5` 偏移是语义）
- [ ] `TacetTask` / `ForgeryTask` 暂不动（新函数忽略传入的 structure）

**验收**：`py_compile` 通过；N≤4 行为与原来一致；N≥5 报错信息明确。

### 阶段 2 · 运行时建表（tag `v0.3-runtime-table`）
**核心改动。只碰 `BaseWWTask`。**

- [ ] 打开列表后确认停在顶部
- [ ] 当场量 `row_h`（相邻按钮 y 差）
- [ ] 从顶部逐步往下扫，**每步滚 2~3 行**（保证 1~2 行重叠）
- [ ] 用**按钮重叠**对齐步与步（上一屏末几行 = 这一屏首几行）
- [ ] 建到第 N 个就停（不需要全表）
- [ ] 不识别标题、不用滑块长度

**验收**：`py_compile`；用 mock 帧驱动，验证 1~23 每个序号都落在正确行。

### 阶段 3 · 接点击（tag `v0.4-click-integrate`）

- [ ] 按表滚到第 N 个附近
- [ ] 重新识别 `boss_proceed`（**保留**，用于点击）
- [ ] **新增边界过滤**：不完整可见的按钮丢弃
- [ ] 点它 → 后续流程完全不动

**验收**：`py_compile`；端到端走一遍 `FarmEchoTask` 的传送分支（不启动游戏，用 mock）。

### 阶段 4 · 实机验证（tag `v0.5-verified`）

- [ ] 启动 OKWW，测**战歌重奏第 5 个**（用户失败场景）
- [ ] 再测 1 / 4 / 6 / 最后一个
- [ ] 讨伐强敌同样
- [ ] **回归**：无音区、凝素领域各一次（确认没退化）
- [ ] 全通过 → 打 tag，写 `v0.5-verified.md`

### 阶段 5 · （后续，未定）提 PR

- [ ] 基于 GitHub master（不是本地 CNB 镜像）
- [ ] 符合 `CONTRIBUTING.md`
- [ ] 附单元测试

## 明确不动

| 项 | 备注 |
|---|---|
| 滑动机制（点轨道） | 能用就不动 |
| `boss_proceed` 模板 | 不重新截取、不改标注 |
| 点击后所有流程 | 选等级、单人挑战、走路进本等 |
| 死亡恢复链路 | 用户标记为不做 |
| `SimulationTask` / `NightmareNestTask` | 不走这条链路 |

## 回退方法

```bash
cd data/apps/ok-ww/working
git checkout v0.2-remove-hardcoded    # 回到任意中间版本
git checkout main                     # 回到 v3.7.4 原始基线
git log --oneline --all --graph       # 看全部版本
```
