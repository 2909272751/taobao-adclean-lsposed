# 淘系去广告 v0.1.1

在 v0.1.0 基础上做了一次**覆盖补强 + 一次自我纠错**，没有改架构。

## 变更

1. **闲鱼弹窗多了一层覆盖**：新增 `com.taobao.idlefish.fun.activepopup.PopupView` 的三个
   `show` 重载（`show()` / `show(String)` / `show(Rect, String)`）。
   这是**另一套**弹窗框架（Weex/H5 + WindVane JS 桥的「活动弹窗」），
   与 v0.1.0 已封的 `PopWindowController`（首页弹窗）**没有调用交叉**。
   闲鱼 `popup` 规则数 3 → 6，总规则数 14 → 17。
2. **淘宝悬浮位多一个 id**：`bootimage_pop_lottie` 加入隐藏清单（开屏浮层 Lottie）。
3. **纠错**：v0.1.0 的交接文档里把 `tb.bbd` 写成「首页弹窗展示控制器」并派了一条
   `tb.bbd#w(int, IPopData)` 的下一步 —— 复核发现 `tb.bbd` 是**滚动容器 interface**
   （`findItemViewByPosition` / `scrollToPositionWithOffset` / `getVisiblePositionRange`），
   根本没有 `w` 方法；`tb.e3b` 的字段类型是 `tb.zbm` 而不是 `tb.bbd`。该条已作废并写进
   `docs/ANALYSIS.md` 的「已被证伪」表。弹窗真正的深层闸门 `tb.e3b#A(int, IPopData)`
   已由 `tb_pop_trigger_data` 覆盖，不需要再加。

## 实测（RMX5060 / Android 16 / LSPosed 1.8.6）

```
(com.taobao.idlefish) [schema=1] feature=splash result=matched armed=5 failed=0
(com.taobao.idlefish) [schema=1] feature=popup  result=matched armed=6 failed=0   <- 新增 3 条已布防
(com.taobao.idlefish) [schema=1] feature=widget result=matched armed=1 failed=0
(com.taobao.idlefish) [schema=1] feature=sdk    result=matched armed=5 failed=0
(com.taobao.idlefish) [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched

(com.taobao.taobao)   [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched
```

新增规则的实际命中行在本轮没有出现（「活动弹窗」是按条件触发的，不是每次启动都有），
状态如实标为**已布防、未观察到命中**。

## 校验

- APK：`taobao-adclean-v0.1.1.apk`，SHA-256 见 `SHA256SUMS.txt`
- 签名与 v0.1.0 相同（本地测试密钥），可直接覆盖安装，不会丢设置

## 已知限制

与 v0.1.0 相同，未变：信息流卡片本体（服务端 DynamicX 模板渲染）与
淘宝闪购频道内的广告不在 `com.taobao.taobao` 的 base.apk 内，本版本不覆盖。
本轮已把 74 个 split APK 全部盘点过（`/data/data/com.taobao.taobao/files/splitcompat/`），
其中 `FlashSalePluginBType.apk` 只是闪购骑手地图动画（AMap + Lottie），不含频道内容。
