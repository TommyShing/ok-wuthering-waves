# 01 · 代码审计（Audit）

审计对象：ok-ww v3.7.4 的 F2 挑战列表定位链路。
审计目的：确认改动范围、影响面、必须保留的约束。

---

## 一、问题现象

「传送至Boss」填第 N 个，实际传送到第 N+1 个（用户实测：填 5，刷到第 6 个）。

## 二、根因（两个错误叠加）

### 错误 1：序号 ≥5 走"估算 + 点最底行"

`src/task/BaseWWTask.py:1153` `click_on_book_target`：

```python
container_max_rows = 4
if serial_number <= container_max_rows:
    target_index = serial_number - 1          # ≤4：精确，取可见第 N 个
else:
    calib_y = bar_top + calib_item_h * serial_number + calib_cross * header_h
    self.click(bar_x, calib_y)                # ≥5：点滚动条轨道估算位置
...
target = max(btns, key=lambda box: box.y)     # 然后点"最下面那一行"
```

- 只能保证"目标被滚到了最底行"，**行距/标题高度/滚动条行程任何误差 = 整行偏移**。
- 纠偏重试 `if not target_index > -1 and ... and structure and ...`（`:1188`）**只在 `structure` 非空时生效**。
- 战歌重奏 / 讨伐强敌传的是 `structure = None`（`FarmEchoTask.py:276`）→ **既无精确映射，也无闭环纠偏**。

### 错误 2：写死的总数已过期

`src/task/FarmEchoTask.py:63-64`：

```python
self.total_weekly_number = 9    # 3.7 实际 11
self.total_boss_number  = 20    # 3.7 实际 23
```

滚动公式 `calib_item_h = calib_container_h / total_number`（`:1181`）
→ 总数偏小 → 以为每项更高 → **滚过头** → 点最底行 → 落到第 N+1 个。

## 三、日志证据

| 时间 | 日志记录序号 | 实际开打的 Boss | 点击的"前往"行 y |
|---|---|---|---|
| 10-16 14:05 | `Weekly Challenge 3`（第4个） | 千傀重楼·渊底遗音 | 729（精确路径） |
| 10-17 00:04 | `Weekly Challenge 4`（第5个） | 辛吉勒姆·星海归航 | 879（最底行，多一行） |

注：`info_set('Teleport to Boss', f'{...} {serial_number - 1}')`（`FarmEchoTask.py:293`）存的是 `serial-1`。

## 四、调用方全貌

`click_on_book_target` 在整个 `working/` 里只有 **3 个调用方**：

| 文件 | 行 | 调用 | structure |
|---|---|---|---|
| `src/task/FarmEchoTask.py` | 298 | `click_on_book_target(book_serial, total_number, structure)` | 战歌/讨伐 = `None`；特异梦魇 = `[5,10]` |
| `src/task/TacetTask.py` | 113 | `click_on_book_target(index + 1, self.total_number, self.structure)` | `[4,5,5,7]` |
| `src/task/ForgeryTask.py` | 65 | `click_on_book_target(serial_number, self.total_number, self.structure)` | `[5,5,5,5]` |

### 不受影响的（已核实）

| 任务 | 为什么不受影响 |
|---|---|
| `SimulationTask` | 自己写死坐标（`:57` `self.click(0.898, 0.533 + index * 0.14)`），**不调用**该函数 |
| `NightmareNestTask` | 用 OCR 数 `x/y` 进度选巢穴（`find_nest` 的 `count_re`），**不调用**该函数 |

### 写死的常量清单

| 常量 | 位置 | 值 |
|---|---|---|
| `total_weekly_number` | `FarmEchoTask.py:63` | 9（实际 11） |
| `total_boss_number` | `FarmEchoTask.py:64` | 20（实际 23） |
| `nightmare_structure` | `FarmEchoTask.py:66` | `[5, 10]` |
| `TacetTask.structure` | `TacetTask.py:18` | `[4, 5, 5, 7]` |
| `ForgeryTask.structure` | `ForgeryTask.py:23` | `[5, 5, 5, 5]` |
| `container_max_rows` | `BaseWWTask.py:1170` | 4 |
| `header_h` | `BaseWWTask.py:1168` | 0.028（拟合值） |
| 重试系数 | `BaseWWTask.py:1191` | 0.55（拟合值） |
| 欠滚阈值 | `BaseWWTask.py:1190` | 0.73（拟合值） |
| `bar_bottom` / `bar_x` | `BaseWWTask.py:1166-1167` | 0.8806 / 0.9730 |

## 五、`structure` 是什么

纯数字列表，描述"从上往下每个地区标题下各有几项"。**不读名字、不认 ID。**

| 页签 | structure | 总数 |
|---|---|---|
| 无音清剿 | `[4,5,5,7]` | 21 |
| 凝素领域 | `[5,5,5,5]` | 20 |
| 战歌重奏 | `[2,2,3,4]` | 11 |
| 讨伐强敌 | `[2,4,7,1,9]` | 23 |
| 特异梦魇 | `[5,10]` | 15（前 5 是巢穴，后 10 是特异梦魇） |

用途：推导每个序号的几何位置（同地区行距 0.1417 屏高；跨地区多 0.0620 标题高）。
**代价**：游戏加行/减行/顶部插行后必须人工改数字，否则错位。

## 六、底层能力现状

### `boss_proceed` 模板

- 标注：`assets/coco_annotations.json` → `images/36.png`，bbox `[1781,404,33,60]`
- 实际是 **33×60 px 的小图标**（一行最右端"前往"按钮的一部分）
- 匹配：`cv2.matchTemplate(..., TM_CCOEFF_NORMED)`，阈值 0.8
- 搜索区：`box_of_screen(0.9113, 0.229, 0.9613, 0.861)` = 每行最右按钮所在的窄竖条
- **只有 1 个样本**，鲁棒性未经过多分辨率/多状态验证

### 地区标题没有 `boss_proceed`

这是关键性质：**数按钮 = 数真条目，天然排除地区标题。**
PR #1640 正是利用"跨地区处按钮 y 间距变大（≈0.0620 屏高）"来识别标题位置。

### 滚动条

- 找法：在深色轨道上找亮色矩形（`book_bar_color` RGB 190~255），最小 3.75×7.5 px
- **当前 v3.7.4 是 hack**：`_find_book_scroll_top`（`:1141`）只在顶部 86px 一条区域里找白块，**从未真正识别滑块长度和位移**
- 滚动方式：**点轨道**（`self.click(bar_x, y)`），不是拖滑块、不是滚轮
- PR #1640 实测规律："滑块靠点击处的那条边会贴到点击处"（edge-follows-click）

### 列表几何（PR #1640 实测，1080p）

| 量 | 值 |
|---|---|
| 行高 `row_h` | 0.1417 × 1080 ≈ 153 px |
| 跨地区额外高度 `header_h` | 0.0620 × 1080 ≈ 67 px |
| 可见高度 | ≈ 0.671 × 1080 ≈ 725 px |
| 一屏可见行数 | 725 / 153 ≈ **4.7 行** |
| 首行 y（普通列表） | 0.3028 |
| 首行 y（战歌重奏） | 0.3574（上方多一行"本周剩余可领取次数"） |

## 七、必须保留的约束

1. **特异梦魇的 `+5` 偏移**：`book_serial = serial_number + sum(structure[:-1])`（`FarmEchoTask.py:297`）。
   前 5 项是梦魇巢穴不是 4C，必须跳过。这是**语义**不是几何，不能一起删。
2. **三个调用方共用同一个函数**，改它必须保证 Tacet/Forgery 不退化。
3. **`SimulationTask` 和 `NightmareNestTask` 不经过此函数**，不受影响。

## 八、不在本次范围

| 项 | 原因 |
|---|---|
| 滑块长度反推总高 | 用户要求先不做，等定位改完实测后再议 |
| 地区标题识别 | 用户要求按原本的来（不识别） |
| 死亡恢复失败即终止 | 用户标记为不做，要自己实测观察 |
| 滑动机制改动 | 用户要求不动（能用就不动） |
| `SimulationTask` / `NightmareNestTask` | 不走这条链路 |
