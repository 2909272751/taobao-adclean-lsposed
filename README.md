<div align="center">
  <img src="assets/logo/logo-192.png" width="112" alt="淘系去广告">
  <h1>淘系去广告 · Taobao Ad Clean</h1>
  <p>LSPosed 模块 · 闲鱼 / 淘宝 开屏广告、首页弹窗、悬浮广告位、广告 SDK 初始化拦截</p>
</div>

---

一个**逐特性可关、未命中时完全不影响目标 App** 的 LSPosed 模块。

- 目标：`com.taobao.idlefish`（闲鱼）、`com.taobao.taobao`（淘宝）
- 框架：LSPosed（libxposed API 102），Android 16 实测
- 只 hook **一次性决策闸门**：不碰 `onDraw` / `onBindViewHolder` / `onScroll` / 动画帧，无轮询、无全树遍历兜底
- 主进程门闸：子进程（推送 / 沙箱 / webview / gpu）一律跳过，不浪费电

## 功能与「对应页面」

| 开关 | 对应页面 | 做了什么 |
|---|---|---|
| 开屏广告 | 冷启动 / 切回前台 / 路由唤起 | 断掉开屏的**全部入口**与**唯一渲染出口**；连广告请求和启动遮罩一起省掉 |
| 弹窗广告 | 首页（登录成功 / 新人引导 / 主容器就绪） | 封堵弹窗装配入口、四条触发路径、PopLayer 服务端准入校验，以及另一套 Weex「活动弹窗」的三个展示入口 |
| 悬浮广告与广告球 | 首页与频道页的浮层广告位 | 按**资源 id 名**隐藏（只隐藏确实存在的那几个 id，找不到就不动） |
| 广告 SDK 初始化与预加载 | 全应用（后台线程） | 关掉第三方开屏 SDK 的初始化与开屏数据预加载，省电省流量 |

四项**默认全部开启**，装完即生效。

## 实测状态（本机 RMX5060 / Android 16 / LSPosed 1.8.6）

逐特性探针结果（`install_summary`，来自 LSPosed 逐模块日志）：

```
闲鱼 7.28.40 (521)  install_summary splash=matched popup=matched widget=matched sdk=matched   (17 条规则，0 失败)
淘宝 10.66.30 (862) install_summary splash=matched popup=matched widget=matched sdk=matched   (18 条规则，0 失败)
```

闸门**真的被调用到**的证据行：

```
(com.taobao.idlefish) blocked id=xy_splash_load_hot      # 切回前台的热启动开屏被拦
(com.taobao.idlefish) hid id/advert_suspend_img          # 首页悬浮广告位被隐藏（该 id 确实存在）
(com.taobao.taobao)   blocked id=tb_pop_init             # 首页弹窗预渲染初始化被拦
(com.taobao.taobao)   blocked id=tb_pop_schedule         # 首页弹窗装配入口被拦
```

淘宝首页视觉对照：装模块前首页浮着「4 张消费券共 … 后到期 · 去使用」倒计时弹窗
（`docs/evidence/taobao-home-before-popup.png`），
装模块后同一入口冷启动，首页正常、该弹窗不再出现（`docs/evidence/taobao-home-after.png`）。

设置页（四行「已布防」+ 每行「对应页面」）：`docs/evidence/module-settings.png`。

开关链路也实测过：在设置页把「广告 SDK」关掉 → 强停闲鱼冷启动 →
`feature=sdk result=off armed=0 failed=0`、`install_summary … sdk=off`；
点「恢复默认设置」→ 该行配置被清掉 → 冷启动恢复 `sdk=matched`。

## 未做到 / 已知限制（不粉饰）

1. **信息流卡片本体没有去掉**。闲鱼与淘宝的首页推荐流由服务端下发的 DynamicX 模板渲染
   （模板 zip 运行时从 OSS 下载，APK 内没有模板代码），两边的 base.apk 里
   **都不存在** `isAd()` / `itemType` / `getCardType` 这类渲染期广告判定（已穷举证伪，见 `docs/RECON-*.md`）。
   所以本模块只清理**有独立容器的浮层广告位**，不去伪造「信息流已清空」。
2. **淘宝闪购（饿了么闪购）频道内的广告**：该频道不在 `com.taobao.taobao` 的 base.apk 内
   （全 APK 无 `shangou`/`sg` 类，只有 `me.ele.taobao.flash.sale.ability.ETFlashSaleAbility`
   这套饿了么 ability IDL）。能生效的只有作用于整个淘宝的开屏 / 弹窗 / 悬浮项。
3. **闲鱼开屏广告在这台设备当前没有广告库存**，因此「广告消失」只能由
   `blocked id=xy_splash_load_hot` 命中行证明闸门生效，没有拿到「广告图消失」的前后截图。

## 安装

1. 下载 Release 里的 `taobao-adclean-v0.1.0.apk` 安装（需要 LSPosed 环境）。
2. 在 LSPosed 管理器里启用「淘系去广告」，作用域勾选**闲鱼**与**淘宝**。
3. **强停**两个目标 App（或点模块设置页里的「强停目标 App」按钮），再打开即生效。

> 开关写在 LSPosed 的 RemotePreferences 里，被 hook 的进程只读；
> 改完必须强停目标 App 才生效（本模块不注册常驻监听，避免额外的耗电）。

## 从源码构建

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\app\build.ps1
```

纯命令行构建（javac → d8 → aapt2 → zipalign → apksigner），不需要 Gradle / Android Studio / 联网。
工具链路径在 `app/build.ps1` 顶部，按需改。

## 文档

- `docs/ANALYSIS.md` —— 每条 hook 的证据表（反编译文件:行 + 形状判据 + 为什么它是闸门）
- `docs/RECON-IDLEFISH.md` / `docs/RECON-TAOBAO.md` —— 完整逆向报告（含「已被证伪」章节）
- `docs/GOAL-HANDOFF.md` —— 当前状态 / 验证证据 / 已证伪假设 / 下一步

## 许可

MIT，见 `LICENSE`。第三方组件见 `THIRD_PARTY_NOTICES.md`。
