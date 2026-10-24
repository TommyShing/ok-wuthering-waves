# F2 书页定位重构 — 项目存档

> 最后更新：2026-10-24
> 状态：**卡在作者批准阶段**（GitHub PR 未提交，仅分支存档）
> 分支：`feat/book-target`

---

## 一、这个项目要解决什么

OK-WW（鸣潮自动化工具）的 F2 挑战列表定位，在游戏版本更新后会**静默点错目标**。

### 症状

用户选「第 N 个 boss」，实际刷的是第 N+1 个。

### 根因

原实现 `click_on_book_target(serial_number, total_number, structure)` 依赖三个手工维护的数字：

```python
# TacetTask
self.structure = [4, 5, 5, 7]        # 每个地区有几项
self.total_number = sum(self.structure)

# FarmEchoTask
self.total_weekly_number = 9         # ← 3.7 实际是 11
self.total_boss_number = 20          # ← 3.7 实际是 23
self.nightmare_structure = [5, 10]
```

游戏增删 boss 后忘记更新这些数字 → 位置算错 → 点到隔壁。

而且代码里还有一堆**拟合常数**：

```python
header_h = 0.028              # 注释自己写着 calibrated
retry_y = to_click_y + item_h * 0.55   # 0.55 是试出来的
if max_y < 0.73:              # 0.73 也是试出来的
```

---

## 二、我们的方案

**不估算，直接识别列表里真实存在的东西。**

### 核心洞察

F2 列表每根栏右边都有一个展开/收起箭头：

- 展开时 **▲**（朝上）
- 收起时 **▼**（朝下）

我们只识别 ▲。所以：

> **把目标栏上方的栏依次收起，屏幕上第一个 ▲ 就是目标栏。**

### 执行步骤

```python
def click_on_book_target(self, bar_index: int, card_index: int):
    # 1) 自下而上收起目标栏上方的栏
    #    （点下面的不影响上面的坐标，所以一次可以点一整屏）
    #    每轮重新识别箭头，直到收起 bar_index - 1 根
    #
    # 2) 第一个 ▲ 就是目标栏
    #    bar_top = arrows[0].center()[1] / self.height - BOOK_BAR_H / 2
    #    卡片从这根栏的真实底边往下排
    #
    # 3) 卡片超出视野底部才滚动
    #    advance = scroll * block_len / view   ← 滚动条比例
    #
    # 4) 在目标卡片那一行里用 boss_proceed 模板找按钮
    #    金色栏（限时提前开放）额外确认一次弹窗
```

### 关键常量（1080p 实测，全部是整数比）

```python
BOOK_BAR_H = 58 / 1080               # 栏高
BOOK_CARD_H = 138 / 1080             # 卡片高
BOOK_GAP_LIST_TOP_BAR = 0.0135       # 列表顶 → 第一根栏
BOOK_GAP_BAR_CARD = 13 / 1080        # 栏 → 卡片
BOOK_GAP_CARD_CARD = 15 / 1080       # 卡片 → 卡片
BOOK_GAP_BAR_BAR = 9.5 / 1080        # 栏 → 栏（收起态，所以收起间距 0.0625）
BOOK_SCROLL_BAR_X = 0.9730           # 滚动条 x
BOOK_SCROLL_BAR_BOTTOM = 0.8806      # 滚动条轨道底
BOOK_ARROW_THRESHOLD = 0.88          # 箭头匹配阈值
```

**验证**：列表顶部推算值 vs 实测值

| 场景 | 推算 | 实测 |
|---|---|---|
| 金色栏（目标第1栏） | 261 | 261 |
| 长滑块（目标第2栏） | 203 | 202 |

误差 ≤1 px。

---

## 三、和 #1640 的关系

[PR #1640](https://github.com/ok-oldking/ok-wuthering-waves/pull/1640)（作者 EEEEEEEEdison）解决**同一个问题**，但路线相反：

| | 我们 | #1640 |
|---|---|---|
| 依赖 `structure` | **不需要** | 核心 |
| 思路 | 识别真实元素 | 让估算更准（实测几何 + 闭环校正） |
| 新增素材 | 箭头模板 | 无 |
| 代码量 | BaseWWTask +146/−77 | +272/−70 |
| 配置项 | **改了**（栏+序号） | 不变 |
| 金色栏弹窗 | ✅ 处理 | ❌ 未处理 |
| 状态 | 分支已推 | Open 2 个月未合 |

**两者互斥。** 如果作者选 #1640，我们这个可以关掉。

### 立场

**不做 `structure` 兼容层。** 这个 PR 的整个意义就是摆脱 `structure`——为了游戏更新时不用维护那串数字。兼容回去等于没做。

---

## 四、改动清单

### 源文件（5 个）

| 文件 | 改动 |
|---|---|
| `src/task/BaseWWTask.py` | `click_on_book_target(bar_index, card_index)` 重写；3 个辅助方法；金色栏确认弹窗 |
| `src/task/TacetTask.py` | 删 `structure`/`total_number`，配置改「栏+序号」 |
| `src/task/ForgeryTask.py` | 同上 |
| `src/task/DailyTask.py` | 同上 |
| `src/task/FarmEchoTask.py` | 同上；特异梦魇固定第 2 栏，只问序号 |

### 辅助方法

```python
def _book_find_arrows(self, frame):
    """返回展开态箭头，从上到下。"""
    return self.find_feature('book_arrow_expanded', frame=frame, limit=0,
                             threshold=BOOK_ARROW_THRESHOLD,
                             box=self.box_of_screen(0.90, 0.13, 0.97, 0.97))

def _book_sliding_block(self, frame):
    """返回滚动条滑块的 (顶, 底)，都是窗口高度比例；列表不用滚动时返回 None。"""
    ...

def _book_bar_is_gold(self, frame, arrow):
    """栏是否为金色（限时提前开放）。采样箭头框顶部几行，避开图标光晕。"""
    ...
```

### 素材（2 个）

- `assets/coco_annotations.json` — 新增 `book_arrow_expanded`（+26 行）
- `assets/images/50.png` — 1920×1080 全屏，模板 36×36

**为什么用全屏图**：作者自己存素材的惯例（`36.png`、`37.png` 都是全屏）。

### i18n

`zh_CN` / `zh_TW` 各 +31 行（`.po`），`.mo` 重新编译。

**特异梦魇复用了作者原有的键**，没有新增翻译：

```
'Which Special Nightmare to Teleport' -> '传送到第几个特异梦魇'
'From Top to Bottom, Starting with 1' -> '从上到下，从1开始'
```

### 测试

| 文件 | 状态 |
|---|---|
| `tests/TestBookTarget.py` | **新增**，15 个用例 |
| `tests/TestFarmEchoTeleport.py` | 已更新（6 通过） |
| `tests/TestDeathReentry.py` | 已更新（12 通过） |

`TestBookTarget` 覆盖：收起顺序、卡片间距、滚动比例、金色栏弹窗、6 种报错场景。

---

## 五、特异梦魇的特殊处理

这个 tab 只有 **2 根栏**：

1. 第 1 根：梦魇巢穴（5 个）
2. 第 2 根：**残像聚落**（特异梦魇 + 梦魇残像）

所以**不需要问用户第几栏**，固定第 2 栏：

```python
elif teleport_to_boss == 'Special Nightmare':
    feature = 'mengyan'
    # The special nightmares are all in the second bar, the first one being the
    # nightmare nests, so only the boss inside that bar is configurable.
    bar_index = 2
    card_index = self.config.get('Which Special Nightmare to Teleport', 1)
```

**这是用户实测反馈后改的**——我最初也问了 Bar，用户说「它没有 Bar 的，就是 Bar 固定是二」。

---

## 六、走过的弯路（别再犯）

### 1. `app.json` 的 `current_version` 不能乱改

我把它从 `v3.7.7` 改成 `v3.7.9`，导致启动器判定「版本不在远端 tag 里」→ **强制更新** → 覆盖整个 `working` 目录，我们的改动全丢。

**真正的判断条件**：

```
current_version_missing = (app.json 的 current_version ∉ working/.git 的 tag 列表)
```

为 `true` 就走 `Forcing update`，**这条路径无视 `MANUAL_UPDATE`**。

**当时的实际情况**：`working/.git` 的 tag 只到 `v3.7.7`（自动更新时没同步新 tag），所以 `v3.7.9` 找不到。

**修复**：用 `pr-v3.7.9` 的 `.git` 替换 `working/.git`，tag 补齐后 `missing=false`，现在设成 `v3.7.9` 是安全的。

### 2. 不要加「检测点击是否生效」

我一度加了 `before` 快照对比，判断箭头有没有变化。**这是多余的**：

- 栏收起后箭头从 ▲ 变 ▼，不再被识别
- 所以下一轮 `arrows` 自然少一个
- 如果 `arrows` 空了，`todo` 就是空，**现有的「栏数不足」分支会触发**

用户原话：「全部收完」和「屏幕上一个可收起的箭头都没有」是**充要条件**。

### 3. 纯图形识别没有好的 fallback

用户原话：

> 我们这个方案就是没什么 fallback 的。那你正常你也不应该什么 fallback 呀，这种纯图形的，你想怎么做这种好的回退吗？做不了的。

点完之后只有两种结果：进错 boss（用户会发现）或找不到按钮（直接报错）。加一层「检测是否点中」是自欺欺人。

---

## 七、已知限制

1. **配置项变了，老配置失效。** 用户需要重新填。这是 breaking change。
2. **多几次点击。** 目标第 N 栏要 N−1 次收起，每次 0.9s。但只在「传送」时付一次。
3. **新增 1.5 MB 素材。**
4. **假设进入时列表在顶部且各栏已展开。** 只识别展开态箭头，如果第 1 栏已收起会数错。重开 F2 页签可满足，但**无法从截图验证**。
5. **只能用于有栏结构的列表。** 单层列表（残像聚落）不适用。
6. **栏内卡片数量无法验证。** 靠模板在目标行里找按钮，找不到会报错。

---

## 八、仓库位置

| 位置 | 用途 |
|---|---|
| `D:\Users\TommyShing\AppData\Local\ok-ww\working\` | **本地开发**，v3.7.9 + 我们的改动，分支 `feat/book-target` |
| `D:\Users\TommyShing\AppData\Local\ok-ww\pr-v3.7.9\` | **PR 基准副本**，干净的 v3.7.9 + 改动，用于恢复 |
| `https://github.com/TommyShing/ok-wuthering-waves` | **GitHub 备份**，分支 `feat/book-target` |

### 关键提交

```
9646317 test(book): cover the bar/card path and update the two affected tests
9ee3d76 fix(book): special nightmare has one bar, so only ask for the boss
e6d6891 refactor(book): keep the whole scroll step in window ratios
9063127 fix(book): measure the list top and scroll by the thumb fraction
2c03b27 feat(book): confirm the early-access warning a gold bar triggers
97f1cf0 refactor(book): anchor cards to the target bar and find the button by template
069cea3 refactor(book): collapse in a while loop driven by the arrow count
8a5550b refactor(book): drop the collapse round cap and read pixels before collapsing
14647c9 feat(book): locate F2 list items by bar/card index
```

### 恢复方法

`working` 被覆盖时：

```powershell
# 从 pr-v3.7.9 复制 12 个文件
# 或从 GitHub 重新拉
git -C D:\Users\TommyShing\AppData\Local\ok-ww\data\apps\ok-ww\working fetch https://github.com/TommyShing/ok-wuthering-waves feat/book-target
```

---

## 九、下一步

**当前卡在作者批准阶段，无人回复。**

GitHub 上有 `feat/book-target` 分支作为存档，本地版本已同步。

### 后续要做的事

1. **等作者回应**（QQ 开发者群 `926858895` / Discord）
2. **在游戏内实测**（尚未完成）
3. **准备 PR 文案**（`_PR.md` 已写好，待补充测试结果和截图）
4. **新分支：改遍历部分** — 梦魇相关的两个任务不是靠单个定位，而是每个都做一遍

### PR 提交前必须补的

- [ ] 识别素材在模板页标注并 Save
- [ ] 运行 `run_test.py` 确认通过
- [ ] 游戏内验证
- [ ] AI 审查（Codex）
- [ ] 联系作者确认方向

---

## 十、参考资料

- [贡献指南](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/docs/development/contributing.md)
- [PR 模板](https://github.com/ok-oldking/ok-wuthering-waves/blob/master/.github/PULL_REQUEST_TEMPLATE.md)
- [PR #1640](https://github.com/ok-oldking/ok-wuthering-waves/pull/1640)
- 作者联系方式：QQ 开发者群 `926858895`、Discord https://discord.gg/vVyCatEBgA
