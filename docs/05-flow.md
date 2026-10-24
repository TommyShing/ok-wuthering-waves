# 05 · 定位与滚动流程

只换 `click_on_book_target` 这一段；F2、页签、点完按钮之后的流程全部沿用作者。

## 0. 前提与边界

- 进入页签时**所有区域都是展开的**，列表在**顶部**
- 只识别 **▲**（展开态）；▼ 不识别
- 不校验 M 是否合法，点错就点错，靠最后的 `wait_feature` 兜底
- 全部几何量都是占窗高/窗宽的比例，运行时乘实际像素

## 1. 常量

| 量 | 比例 | 说明 |
|---|---|---|
| `BAR_H` | 0.05370 | 区域栏高 |
| `CARD_H` | 0.12778 | 卡片高 |
| `G1` | 0.01204 | bar → card |
| `G3` | 0.01389 | card → card |
| `CARD_PITCH` | 0.14167 = `CARD_H + G3` | 卡片节距 |
| `BAR_PITCH_C` | 0.06250 | **全收起时**栏节距 |
| `PAD` | 0.0135 | 列表顶 → 第 1 根栏顶 |
| `ARROW_X` | 0.94219 | 箭头横坐标 |
| `BUTTON_X` | 0.8956 | 「直接挑战」按钮中心 |
| `BAR_X` | 0.9730 | 滚动条横坐标（作者） |
| `TRACK_BOTTOM` | 0.8806 | 轨道底（作者，已验证差 1 px） |

## 2. 定位

```
1  扫 ▲ → 箭头中心 y 列表；最上面那个就是第 1 根栏
   bar1_top = arrow[0].cy - BAR_H/2
2  TRACK_TOP = 作者法找到的滑块顶（独立，和列表定位无关）
3  c = 0
   while True:
       arrows = 扫 ▲
       if not arrows: raise IndexError(N 超出实际栏数)
       todo = [i for i in (c+1 .. c+len(arrows)) if i < N]
       if not todo: break            # 最上面那个 ▲ 就是第 N 根
       从下往上点 todo 里的箭头        # 坐标不受前面点击影响
       c += len(todo)
4  第 N 根栏保持展开（它从来没被点过）
   barN_top = bar1_top + (N-1) * BAR_PITCH_C
   list_top = bar1_top - PAD
```

## 3. 卡片位置

```
to_bottom = PAD + (N-1)*BAR_PITCH_C + BAR_H + G1 + (M-1)*CARD_PITCH + CARD_H
```

`to_bottom` = 从列表顶到目标卡底边的距离（内容坐标系）。

## 4. 滚动分支

只有 `to_bottom > V` 才进。

```
V      = TRACK_BOTTOM - TRACK_TOP          # 轨道长（视口高的近似）
C      = V*V / L                           # 内容总高，由滑块长 L 反推
S      = to_bottom - V                     # 需要滚动的距离
f      = clamp(S/(C-V), 0, 1)
travel = V - L

短滑块（中点仍在轨道里）:
    L = 二分找「底」- TRACK_TOP
    y = TRACK_TOP + f*travel + L           # 点滑块下方 → 底落到 y

长滑块（中点还在滑块里）:
    先点 TRACK_BOTTOM 推到底
    L = TRACK_BOTTOM - 二分找「顶」
    y = TRACK_TOP + f*travel               # 点滑块上方 → 顶落到 y

click(BAR_X, y)
```

两个分支**都不需要复位**：短滑块本来就在顶部，长滑块推到底后目标一定在它上方，
「点在滑块上方 / 下方」的规则天然成立。

滚完目标卡底边正好贴视口底。

## 5. 点击

```
y_click = list_top + V - CARD_H/2          # 滚过
y_click = list_top + to_bottom - CARD_H/2  # 没滚
click(BUTTON_X, y_click)
```

之后接作者的 `wait_feature(['fast_travel_custom', 'gray_teleport', 'remove_custom', 'team_close'])`。

## 6. 尚未验证

1. 长短判据在「长滑块」下的实际表现（二分仍在全流程里一起验）
2. `V` 用的是轨道长，视口高略大（S1 里差 11 px），影响约 1.5%
3. 复位到「正顶部」不可达（轨道顶那一排命中区被圆角内缩），但本流程不需要复位

## 7. 已知问题（不在本次范围）

**队友倒地后卡在「是否使用治疗药」页面**

现象：脚本点到已经倒下的队友 → 进入询问是否用治疗药复活的页面 → 卡住 →
后面扫不到敌人 → 被当作脱战 → 反复重开，永远打不完。

期望：进入该页面就应该被判为「队友倒地」，然后按已合并 PR 的方案处理——
先退出，再以该角色为基点找附近的传送锚点，传送过去治疗。

未做原因：判定点在作者的战斗/复活流程里（`raise_not_in_combat` → `revive_action`），
耦合度高、改动面大，与本次定位修改无关。

## 8. 测试序列（战歌重奏）

| 用例 | N | M | 意图 |
|---|---|---|---|
| 1 | 3 | 1 | 前两个区域收起，目标区第一张卡 |
| 2 | 5 | 4 | 前四个区域收起，目标区第四张卡（大概率要滚动） |
