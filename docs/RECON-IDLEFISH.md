# 闲鱼 7.28.40 去广告锚点候选

分析对象：`reference-apk/idlefish-7.28.40-base.apk`（闲鱼 7.28.40，versionCode 521，包名 `com.taobao.idlefish`，113 MB，9 个 dex，90404 个类，550939 个 method_id）。
本次为**只读静态分析**：未修改任何 Java 源码，未安装任何东西。全部结论来自 jadx 1.5.5 单类反编译产物（`scratch-recon/jadx-xy/`，54 个类）与 dex 级分析工具（`tools/dex_meta.py`、`tools/dex_scan.py`、`tools/arsc_scan.py`）。

## 结论摘要

1. **开屏广告**走闲鱼自建链路，与阿里妈妈 XAd SDK 无直接调用关系：`MainPageJumpWorkflow.jump()` → `Advert.showMaybe(Activity)`（Advert.java:18）→ `Advert$$ExternalSyntheticLambda0.run()` → `SplashAdController.loadSplashAd(Activity)`（SplashAdController.java:342）→ `requestAndShow(...)`（:267）→ MTop `SplashAdResp` 回包 → `handleSuccessResponse` 里**唯一一处**决定要不要展示的代码：`splashAdResp.getAdapterKey()`（:166）非空才 `SplashAdAdapter.showSplashAd(...)`（:168）；为空则走 `dismissCover()` 无广告路径（:189）。
2. 闲鱼开屏**五路 DSP 全接**：`SplashAdAdapterFactory` 注册表（SplashAdAdapterFactory.java:10-14）为 `mama`(阿里妈妈)、`toc`(闲鱼自有)、`beizis`(BeiZi)、`ylh`(优量汇/GDT)、`csj`(穿山甲)；由服务端 `SplashAdResp.getAdapterKey()` 决定用哪家。**五家最终都汇聚到同一个渲染出口** `SplashAdShower.showSplashAd(Activity, View, boolean)`（SplashAdShower.java:89）。
3. **首页弹窗广告**走另一条链，与开屏完全独立：`PopMainWorkflow.idleRun()`（PopMainWorkflow.java:77/81）与 `MainPageJumpWorkflow`（:256/:269）→ `AbsPopWindowController.requestAndShowPopWindow(long)`（接口 AbsPopWindowController.java:17，实现 PopWindowController.java:283）→ `doHandleShowPopWindow()`（:220）→ 仅当 `PopWindowConfig.pop == true` 且 url 非空才 `showPopWindow(String)`（:230）。请求侧在 `PopWindowRequestController.request(ContextWrapper, boolean, ApiCallBack)`（PopWindowRequestController.java:53）。
4. **信息流广告没有 Java 侧渲染闸门**。首页/搜索/推荐卡片的展示由服务端下发的 DynamicX(DX) 模板决定（模板 zip 运行时从 OSS 下载，APK 内无模板），Java 里唯一的"这是不是广告"判断是 `SecondPartyAdHelper.isSecondPartyAdType(JSONObject)`，而它的**全部 4 个调用点都在 DX 卡片点击事件处理器**里（埋点用），不在渲染路径上。故信息流的可行锚点是资源 id 隐藏（item 4）而非 Java 方法 hook。
5. 可用的**非混淆开关类**已确认存在：`com.taobao.fleamarket.swtch.NewSplashAdOrange`（thirdCsjOn/thirdYlhOn/thirdAdPlusOn/splashCoverOn/disableHotStart，NewSplashAdOrange.java:252/273/280/231/34）与 `com.taobao.idlefish.fishad.FishAdOrangeManager`。前者在三个厂商 adapter 内就是硬门闸（SplashAdCsjAdapter.java:28、SplashAdYlhAdapter.java:25、SplashAdBeizisAdapter.java:30）。

## 候选锚点表

| # | 目标现象 | 类#方法（完整签名） | 形状判据 | 证据（反编译文件:行） | 为什么它是闸门 | 置信度 |
|---|---|---|---|---|---|---|
| 1 | 开屏广告（全 DSP 通杀，且不残留遮罩） | `com.taobao.fleamarket.splashad.protocol.SplashAdResp#getAdapterKey() : java.lang.String`（public 实例方法，非 static，无参） | 返回 String；返回 `null` 即"无广告" | 方法体 SplashAdResp.java:42-50（`:49 return null`）；调用点与判定 SplashAdController.java:166-170；无广告分支 SplashAdController.java:189 | 唯一调用点写成 `String adapterKey = splashAdResp.getAdapterKey(); if (adapterKey != null && (adapter = SplashAdAdapterFactory.get(adapterKey)) != null) { adapter.showSplashAd(...); z2 = true; }`；`z2 == false` 时执行 `SplashAdShower.dismissCover()` + `requestAsyncSplashAd`，即 **返回 null 就确定性地走"不展示 + 撤掉遮罩"路径**，覆盖全部五家 DSP | 高 |
| 2 | 开屏广告（DSP 无关的渲口总闸） | `com.taobao.fleamarket.splashad.SplashAdShower#showSplashAd(android.app.Activity, android.view.View, boolean) : void`（public final 实例方法） | 三参 `(Activity, View, Z)` → `void`；单例 `SplashAdShower.instance()` | 定义 SplashAdShower.java:89；五家调用点：SplashAdCsjAdapter.java:129、SplashAdYlhAdapter.java:137、SplashAdBeizisAdapter.java:128、SplashAdMamaAdapter.java:38、SplashAdToCAdapter.java:71 | 五路 DSP 的 view 各自构造完后**全部**调用这一个方法（调用者集合由 `--callers-of` 穷举得出，另有 `SplashAdActivity.java:21` 一条），hook 它空实现即任何 DSP 都渲染不出开屏广告 | 高 |
| 3 | 开屏广告（配置级，非混淆、跨版本最稳） | `com.taobao.fleamarket.swtch.NewSplashAdOrange#thirdCsjOn() : boolean`、`#thirdYlhOn() : boolean`、`#thirdAdPlusOn() : boolean`（均 static public，无参） | 三者都 `() → Z`，包装 `SharedPreferences("splash_ad_orange").getBoolean(key, true)` | 定义 NewSplashAdOrange.java:273 / :280 / :252；**硬门闸用法**：SplashAdCsjAdapter.java:28 `if (!thirdCsjOn()) { ...; return; }`、SplashAdYlhAdapter.java:25、SplashAdBeizisAdapter.java:30 | 三个厂商 adapter 在**发起加载前**就用这三个开关短路返回，等于闲鱼自带的"关掉某家开屏"开关；改返回 false 即该 DSP 永不请求、永不展示，且不需要理解各 SDK | 高 |
| 4 | 开屏广告（冷启动入口，链路最短） | `com.taobao.fleamarket.advert.Advert#showMaybe(android.app.Activity) : void`（static public） | `(Activity) → void`，static | 定义 Advert.java:18-33；内部 `:27` new lambda、`:28` 判 `NewSplashAdOrange.splashCoverOn()`；lambda → `SplashAdController.loadSplashAd` 由 `--callers-of` 证明为**唯一**调用者（scratch-recon/callers-B.txt:4） | 冷启动开屏唯一入口；`:22-26` 已有"首次安装不展示"的早退分支，说明此处就是"要不要展示"的决策点，空实现后连遮罩和广告请求都不会发生 | 高 |
| 5 | 开屏遮罩/占位图（SplashAdDialog 那层白屏） | `com.taobao.fleamarket.splashad.SplashAdController#loadSplashAd(android.app.Activity) : void` | `(Activity) → void`，public final 实例方法 | 定义 SplashAdController.java:342-355；其中 `:346`/`:351` 调 `SplashAdShower.showCover(activity)`；调用者清单见 scratch-recon/callers-B.txt:6-8 | 该方法同时是"显示遮罩"和"发起广告请求"的共同起点。若只 hook 锚点 2，遮罩仍会显示：`showCover` 投递 `SplashAdDialog$$ExternalSyntheticLambda1`（SplashAdShower.java:81）→ 该 runnable 用 `NewSplashAdOrange.splashCoverTimeout()`（默认 3000ms，NewSplashAdOrange.java:238-242；`--callers-of` 证明其唯一调用者就是该 runnable）延后触发 `SplashAdDialog.$r8$lambda$W1LKhsOoWxMlEyb7UdJRfDkKZPg`（SplashAdDialog.java:12-21，日志 `FakeViewRemoved`）才撤除。本锚点可彻底消除这段白屏 | 高 |
| 6 | 开屏（"假装已在展示"式拦截） | `com.taobao.fleamarket.splashad.SplashAdController#isSplashAdShowing() : boolean`（public final 实例方法，无参） | `() → Z`，非 static | 定义 SplashAdController.java:338-340；唯一调用点 SplashAdController.java:269 `if (isSplashAdShowing()) { ...; return; }`（callers-B.txt 确认仅 1 个调用者） | `requestAndShow` 第一条语句即判它，返回 true 则整个冷/热启动开屏逻辑直接返回，不发请求、不显示遮罩 | 中（副作用：真实值由 SplashAdDialog.java:63/86 维护，恒真会污染 `addActionAfterSplashAd`/埋点判断） |
| 7 | 开屏热启动 | `com.taobao.fleamarket.splashad.SplashAdController#loadSplashAdHotStart() : void` | `() → void`，public final 实例方法 | 定义 SplashAdController.java:357-382；唯一调用者 `SplashAdController$1.onAppForeground()`（SplashAdController.java:238，callers-B.txt:13-14） | 冷启动以外的切回前台开屏唯一入口；锚点 4 只覆盖冷启动，要全免必须连它一起处理 | 中 |
| 8 | 开屏（ToC 分享/路由拦截路径） | `com.taobao.fleamarket.splashad.SplashAdController#loadToCSplashAd() : void` | `() → void`，public final 实例方法 | 定义 SplashAdController.java:384-386；调用者 `com.taobao.idlefish.router.interrupter.pre.RouterInterrupterSplashAd.checkInterrupt(Context, String, IRouteRequest)`（callers-B.txt:16-20） | 路由跳转时强制走开屏的第三条入口（ToC 自有广告位），锚点 4/7 覆盖不到 | 中 |
| 9 | 首页弹窗广告（真正决定"弹不弹"的那一步） | `com.taobao.idlefish.popwindow.PopWindowController#doHandleShowPopWindow() : void`（包级私有 final 实例方法） | `() → void` | 定义 PopWindowController.java:220-235；门闸读取 `:224 boolean z = popWindowConfig.pop;`、`:226 if (z && StringUtil.isNotBlank(str))`、`:230 showPopWindow(str)`；调用者 2 个（scratch-recon/callers-popup.txt:9-12） | 弹窗展示的唯一决策点：`pop` 标志为 false 或 url 为空则**不显示**，只上报 `reportSuccess`；数据结构 `PopWindowConfig` 的字段已确认为 `Z pop` / `Z showClose` / `I scene` / `String url`（`--fields-of` 实测） | 高 |
| 10 | 首页弹窗广告（所有触发源的统一入口） | `com.taobao.idlefish.maincontainer.AbsPopWindowController#requestAndShowPopWindow(long) : void`（接口方法；实现 `com.taobao.idlefish.popwindow.PopWindowController#requestAndShowPopWindow(long) : void`） | `(J) → void` | 接口 AbsPopWindowController.java:17；实现 PopWindowController.java:283-300；调用点：MainPageJumpWorkflow.java:256（登录成功后）、:269（首次启动登录引导）、PopMainWorkflow.java:81（`idleRun` 延迟 3000ms）（callers-popup.txt:1-7） | 三个触发源（登录成功/新人引导/主容器 idle）全部经此接口进入弹窗链路，空实现即全弹窗屏蔽 | 高 |
| 11 | 首页弹窗广告（连网络请求一起省掉） | `com.taobao.idlefish.popwindow.PopWindowRequestController#request(android.content.ContextWrapper, boolean, com.taobao.idlefish.protocol.net.ApiCallBack) : void` | `(ContextWrapper, Z, ApiCallBack) → void` | 定义 PopWindowRequestController.java:53；唯一调用者 `PopWindowController.$r8$lambda$SC3JVtGV2wCDyQ9Flp9U2nIXzDs`（callers-popup.txt:17-19） | 弹窗配置的 MTop 拉取点，空实现后无配置可弹（`popWindowConfig` 保持 null，`doHandleShowPopWindow` 的 `!= null` 判定失败），且节省一次网络请求 | 高 |
| 12 | 开屏（第三方 SDK 初始化，最上游） | `com.taobao.fleamarket.advert.AdvertiseSplash#init(android.app.Application) : void`（static public） | `(Application) → void`，static | 定义 AdvertiseSplash.java:11-62；`:20 com.alimm.xadsdk.AdSdkManager.getInstance().init(...)`；调用者 `com.idlefish.blink.BlinkNodeNewJoint.com_taobao_fleamarket_advert_AdvertiseSplash_init_main / _pull`（callers-B.txt:74-76） | 阿里妈妈 XAd SDK 的唯一初始化入口（`@ExecNewInit` prefer=91，main+pull 双进程），空实现可让 Mama 系广告整体不可用 | 中（属 SDK 初始化级，影响面大于"开屏"，优先用锚点 3） |
| 13 | 开屏（穿山甲/优量汇 SDK 初始化） | `com.taobao.fleamarket.splashad.tool.ThirdSdkUtil#initCsjSdk(SdkInitListener) : void`、`#initYlhSdk(SdkInitListener) : void`（均 static public） | `(SdkInitListener) → void`，static | 定义 ThirdSdkUtil.java:11（`:24 TTAdSdk.init`、`:25 TTAdSdk.start`）与 :45（`:59 GDTAdSdk.initWithoutStart`、`:60 GDTAdSdk.start`）；调用者 SplashAdCsjAdapter.java:40、SplashAdYlhAdapter 同构 | 穿山甲与优量汇的唯一 SDK 启动入口；不改它则 SDK 仍被拉起并做后台初始化（耗电/流量） | 中 |

## 已反编译的类清单

全部产物在 `scratch-recon/jadx-xy/`（54 个类）。映射：`<类全名> → <文件>`。

| 类全名 | 文件 |
|---|---|
| com.taobao.fleamarket.splashad.SplashAdController | `scratch-recon/jadx-xy/SplashAdController.java` |
| com.taobao.fleamarket.splashad.SplashAdShower | `scratch-recon/jadx-xy/SplashAdShower.java` |
| com.taobao.fleamarket.splashad.SplashAdDialog | `scratch-recon/jadx-xy/SplashAdDialog.java` |
| com.taobao.fleamarket.splashad.SplashAdActivity | `scratch-recon/jadx-xy/SplashAdActivity.java` |
| com.taobao.fleamarket.splashad.SplashAdTransformer | `scratch-recon/jadx-xy/SplashAdTransformer.java` |
| com.taobao.fleamarket.splashad.manager.SplashAdCacheManager | `scratch-recon/jadx-xy/SplashAdCacheManager.java` |
| com.taobao.fleamarket.splashad.manager.SplashAdAssetManager | `scratch-recon/jadx-xy/SplashAdAssetManager.java` |
| com.taobao.fleamarket.splashad.monitor.SplashAdLaunchFunnel | `scratch-recon/jadx-xy/SplashAdLaunchFunnel.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAd | `scratch-recon/jadx-xy/SplashAd.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdResp | `scratch-recon/jadx-xy/SplashAdResp.java` |
| com.taobao.fleamarket.splashad.protocol.SplashRealTimeAd | `scratch-recon/jadx-xy/SplashRealTimeAd.java` |
| com.taobao.fleamarket.splashad.protocol.SplashCacheAd | `scratch-recon/jadx-xy/SplashCacheAd.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdReqAbs | `scratch-recon/jadx-xy/SplashAdReqAbs.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdReqAsync | `scratch-recon/jadx-xy/SplashAdReqAsync.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdReqSync | `scratch-recon/jadx-xy/SplashAdReqSync.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdSpaceIdMap | `scratch-recon/jadx-xy/SplashAdSpaceIdMap.java` |
| com.taobao.fleamarket.splashad.protocol.SplashAdConfig | `scratch-recon/jadx-xy/SplashAdConfig.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdAdapterFactory | `scratch-recon/jadx-xy/SplashAdAdapterFactory.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdAdapter | `scratch-recon/jadx-xy/SplashAdAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdAbsAsyncAdapter | `scratch-recon/jadx-xy/SplashAdAbsAsyncAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdAbsSyncAdapter | `scratch-recon/jadx-xy/SplashAdAbsSyncAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdMamaAdapter | `scratch-recon/jadx-xy/SplashAdMamaAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdCsjAdapter | `scratch-recon/jadx-xy/SplashAdCsjAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdYlhAdapter | `scratch-recon/jadx-xy/SplashAdYlhAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdBeizisAdapter | `scratch-recon/jadx-xy/SplashAdBeizisAdapter.java` |
| com.taobao.fleamarket.splashad.splashadapter.SplashAdToCAdapter | `scratch-recon/jadx-xy/SplashAdToCAdapter.java` |
| com.taobao.fleamarket.splashad.tool.ThirdSdkUtil | `scratch-recon/jadx-xy/ThirdSdkUtil.java` |
| com.taobao.fleamarket.splashad.tool.ConfigCache | `scratch-recon/jadx-xy/ConfigCache.java` |
| com.taobao.fleamarket.splashad.view.SplashAdViewNew | `scratch-recon/jadx-xy/SplashAdViewNew.java` |
| com.taobao.fleamarket.splashad.view.SplashAdToCView | `scratch-recon/jadx-xy/SplashAdToCView.java` |
| com.taobao.fleamarket.advert.Advert | `scratch-recon/jadx-xy/Advert.java` |
| com.taobao.fleamarket.advert.AdvertiseSplash | `scratch-recon/jadx-xy/AdvertiseSplash.java` |
| com.taobao.fleamarket.advert.InitActivityStartEvent | `scratch-recon/jadx-xy/InitActivityStartEvent.java` |
| com.taobao.fleamarket.swtch.NewSplashAdOrange | `scratch-recon/jadx-xy/NewSplashAdOrange.java` |
| com.taobao.fleamarket.swtch.SplashAdPrefetchSwitch | `scratch-recon/jadx-xy/SplashAdPrefetchSwitch.java` |
| com.taobao.idlefish.workflow.MainPageJumpWorkflow | `scratch-recon/jadx-xy/MainPageJumpWorkflow.java` |
| com.taobao.idlefish.workflow.PopMainWorkflow | `scratch-recon/jadx-xy/PopMainWorkflow.java` |
| com.taobao.idlefish.maincontainer.AbsPopWindowController | `scratch-recon/jadx-xy/AbsPopWindowController.java` |
| com.taobao.idlefish.maincontainer.IPopWindowContainer | `scratch-recon/jadx-xy/IPopWindowContainer.java` |
| com.taobao.idlefish.popwindow.PopWindowController | `scratch-recon/jadx-xy/PopWindowController.java` |
| com.taobao.idlefish.popwindow.PopWindowRequestController | `scratch-recon/jadx-xy/PopWindowRequestController.java` |
| com.taobao.idlefish.router.interrupter.pre.RouterInterrupterSplashAd | `scratch-recon/jadx-xy/RouterInterrupterSplashAd.java` |
| com.taobao.idlefish.fun.activepopup.ActivePopup | `scratch-recon/jadx-xy/ActivePopup.java` |
| com.taobao.idlefish.fun.activepopup.PopupView | `scratch-recon/jadx-xy/PopupView.java` |
| com.taobao.idlefish.fun.activepopup.PopupConfig | `scratch-recon/jadx-xy/PopupConfig.java` |
| com.taobao.idlefish.fun.activepopup.PopupContext | `scratch-recon/jadx-xy/PopupContext.java` |
| com.taobao.idlefish.fun.activepopup.PopupNeedPage | `scratch-recon/jadx-xy/PopupNeedPage.java` |
| com.taobao.idlefish.fun.activepopup.PopupApiPlugin | `scratch-recon/jadx-xy/PopupApiPlugin.java` |
| com.alimm.xadsdk.business.splashad.SplashAdController | `scratch-recon/jadx-xy/SplashAdController.java`（与闲鱼同名类冲突，实际落盘为闲鱼版本；xadsdk 版本见下方说明） |
| com.alimm.xadsdk.business.splashad.SplashAdModel | `scratch-recon/jadx-xy/SplashAdModel.java` |
| com.alimm.xadsdk.business.splashad.SplashAdConfig | `scratch-recon/jadx-xy/SplashAdConfig.java` |
| com.alimm.xadsdk.business.splashad.FocusAdController | `scratch-recon/jadx-xy/FocusAdController.java` |
| com.alimm.xadsdk.business.splashad.VbCacheManager | `scratch-recon/jadx-xy/VbCacheManager.java` |
| com.bytedance.sdk.openadsdk.TTAdSdk | `scratch-recon/jadx-xy/TTAdSdk.java` |
| com.bytedance.sdk.openadsdk.TTAdNative | `scratch-recon/jadx-xy/TTAdNative.java` |
| com.qq.e.comm.managers.GDTAdSdk | `scratch-recon/jadx-xy/GDTAdSdk.java` |

> 落盘说明：`--single-class-output` 以**简单类名**命名文件，因此 `com.taobao.fleamarket.splashad.SplashAdController`、`com.alimm.xadsdk.business.splashad.SplashAdController`、`com.taobao.fleamarket.splashad.protocol.SplashAdConfig` 与 `com.alimm.xadsdk.business.splashad.SplashAdConfig` 等**同名不同包**的类会互相覆盖，先落盘者保留（本表已按实际内容标注）。因此我给每个类都补了 dex 级方法清单作为不依赖文件名的第二证据来源。

## 已被证伪 / 不成立的猜测

以下几项经实际验证**不成立**，记录在此避免重复试验。

1. **"闲鱼只接一家开屏 SDK，找那家的 SplashAd 即可"——不成立。** `SplashAdAdapterFactory`（SplashAdAdapterFactory.java:10-14）静态注册了 5 个 adapter：`mama`/`toc`(同步组，:38-48)、`beizis`/`ylh`/`csj`(异步组，:26-36)，由服务端 `SplashAdResp.getAdapterKey()` 决定。同时 APK 内实际存在 5 家 SDK 代码：`com.bytedance.sdk.openadsdk.*`（穿山甲）、`com.qq.e.*`（优量汇）、`com.beizi.*`（BeiZi）、`com.alimm.xadsdk.*`（阿里妈妈）、`com.insightvision.openadsdk.*`（FanTiAds，`com.insightvision.openadsdk.api.FanTiAdSdk`，非开屏用）。hook 任何单一厂商 SDK 都拦不住开屏，必须用锚点 1/2/3/4。
2. **"`com.alimm.xadsdk.business.splashad.SplashAdController` 是开屏总控"——不成立。** 该类的公开 API 只有 `getAdAsync(Map, Callback)` / `getAdSync()` / `onAdStart/onAdSkip/onAdFinish/onAdError` / `setColdStart(boolean)` / `dispose()`，且**没有任何闲鱼类调用它的方法**（`--callers-of` 对 4 个疑点方法均返回 0 调用点）。它只被闲鱼当作 Mama adapter 内部使用的 SDK，不是闲鱼的调度中枢；闲鱼的中枢是 `com.taobao.fleamarket.splashad.SplashAdController`（同名不同包）和 `com.taobao.fleamarket.advert.Advert`。
3. **"`Advert.isShowAdvert()` 是弹窗闸门"——不成立。** `Advert.java:36-38` 只 `return sIsShowing`，而 `sIsShowing` 由 `setIsShowing(boolean)` 在 `SplashAdDialog.java:62`/`:85` 设置，是**开屏显示状态的回读**（`@Chain(base = IAdvert.class)` 暴露给其他模块查询），`--callers-of` 对 `Advert#isShowAdvert` 返回 **0 调用点**。它不决定是否展示，hook 它没有去广告效果。
4. **"`Advert.showMaybe()` 是首页弹窗广告入口"——不成立。** `Advert.java:18-33` 的路径经 lambda 指向 `SplashAdController.loadSplashAd`（callers-B.txt 证明为唯一调用者），属**开屏**链路；首页弹窗走的是 `PopWindowController`（见锚点 9/10/11），两条链无交叉。
5. **"信息流广告卡片有 Java 侧 `isAd()` 判定方法"——不成立。** 实测：`--string-refs` 仅命中 `SecondPartyAdHelper.isSecondPartyAdType(JSONObject)` 一处与 `adType` 相关的判断方法，而它的**全部 4 个调用点都在 DX 卡片点击事件处理器**里：`DXRecommendCardTapEventHandler.onEvent`（详情页推荐流）、`DXPersonalRecommendCardTapEventHandler.onEvent`（个人页推荐流）、`SearchDXCardTapEventHandler.onEvent`（搜索结果）、`TapADJumpUrlEventHandler.onEvent`（首页广告跳转），且都是 `invoke-static` 用于点击埋点，**不在渲染/数据装配路径上**。首页信息流本身是服务端下发的 DX 段落（`mtop.taobao.idle.home.moore.section`，其 JSON 内广告项以 `itemBizCode`/`clickParam.args.adsTaskId` 标识，模板 zip 运行时从 `ossgw.alicdn.com` 下载，APK 里没有模板代码），所以渲染期"去广告"无法用 Java 方法 hook 实现。
6. **`ad_splash_enable` / `ad_enable` 不是 Java 侧开关。** 这两个字符串确实存在于 dex 字符串表（`tools/dex_scan.py --string-re` 命中），但 `--string-refs` 扫遍全部 437318 个 code_item 后**没有任何方法用 `const-string` 加载它们**，说明它们由 weex/JS bundle 或 native 侧使用，不能作为 Java hook 锚点。（该扫描器已用已知串 `SplashAdTrace-showCover` 自校验，确认能命中 SplashAdShower 内的加载点。）
7. **`IPopWindowContainer#show()` 不宜作锚点。** `--callers-of` 返回"NO CALLER"，它是接口方法、由容器实现类多态分派，静态无法穷举调用点，改它不如直接拦锚点 9/10。

## 本次新增的可复用工具（只读）

| 工具 | 用途 |
|---|---|
| `tools/dex_meta.py` | dex 级方法/字段签名清单、**调用者穷举**（`--callers-of`，单遍扫描全部 code_item）、类引用（`--xref-class`）、字符串加载点定位（`--string-refs`）。指令遍历含 `0x18 const-wide` 宽度与 switch / fill-array-data **payload** 跳过逻辑，已对全部 9 个 dex 的 437318 个 code_item 验证**逐条精确走到 `insns_size`，0 处 desync**。 |
| `tools/arsc_scan.py` | 不依赖 jadx 直接解析 `resources.arsc`，输出 `0xRRTTEEEE` + `type/name` 形式的资源条目名（`--type id` / `--name-re`）。`jadx -r` 跳资源，故资源 id 名必须走这里。 |
| `scratch-recon/run-jadx.ps1` | jadx 批量单类反编译（注意：本机只有 Windows PowerShell 5.1，须用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File` 调用，且 `.ps1` 含中文路径时须存为 UTF-8 **带 BOM**）。 |
| `scratch-recon/callers-B.txt`、`callers-popup.txt`、`meta-A/B/C.txt` | 本次全部调用者/签名证据原始输出。 |

### 4. 资源 id 名候选（来自 `tools/arsc_scan.py` 实测）

闲鱼自有（0x7f09xxxx 段，非厂商 SDK 前缀）的广告相关条目：

| 资源 id | 名称 | 推测用途 |
|---|---|---|
| 0x7f0900e1 | `id/advert_suspend_layout` | 悬浮/挂件广告根容器 |
| 0x7f0900e2 | `id/advert_suspend_stub` | 悬浮广告 ViewStub |
| 0x7f0900e0 | `id/advert_suspend_img` | 悬浮广告图 |
| 0x7f0900de / 0x7f0900df | `id/advert_suspend_countdown` / `..._layout` | 悬浮广告倒计时 |
| 0x7f0900d4 / 0x7f0900d5 / 0x7f0900d6 | `id/adball` / `id/adball_close` / `id/adball_layout` | 广告球 |
| 0x7f0900cb / 0x7f0900cc / 0x7f0900cd | `id/ad_tag` / `id/ad_tag_text` / `id/ad_tag_wrapper` | 卡片"广告"角标（信息流判定用） |
| 0x7f0900c8 | `id/adView` | 通用广告容器 |
| 0x7f0900ce / 0x7f0900cf | `id/ad_web_close_view` / `id/ad_web_view_container` | 广告落地页 WebView |
| 0x7f0900c9 / 0x7f0900ca | `id/ad_detail_uc_progress` / `id/ad_detail_uc_tool_container` | 详情页广告位 |

开屏相关 layout：`layout/splash_ad_view`(0x7f0c0769)、`layout/splash_ad_view_new`(0x7f0c076a)、`layout/splash_ad_third_view`(0x7f0c0767)、`layout/splash_ad_to_c_view`(0x7f0c0768)。
弹窗相关 layout：`layout/layout_pop_window`(0x7f0c05af)、`layout/uppop_window`(0x7f0c07c4)、`layout/downpop_window`(0x7f0c0370)。

> 这些 id 名里 `fanti_*`/`beizi_*` 段已确认属第三方 SDK（已从表中剔除）。上表条目均落在闲鱼自有资源段，但**是否在当前版本的首页/搜索页真实出现、以及同一页面出现几次，必须按目标机 `uiautomator dump` 复核后再用于隐藏**——id 名跨版本可能被复用，且"卡片容器/标题"类 id 最易误伤。

## 下一步建议

1. 落模块时优先用**锚点 1（`SplashAdResp.getAdapterKey()` 返回 null）+ 锚点 3（三个 `NewSplashAdOrange` 开关返回 false）**：前者单点覆盖五路 DSP 且天然走"撤遮罩"分支，后者是非混淆开关、跨版本存活率最高，且两者都不触碰高频路径。
2. 弹窗用**锚点 10（`AbsPopWindowController.requestAndShowPopWindow(long)` 空实现）**，并同时对锚点 11 的 `PopWindowRequestController.request(...)` 兜底（避免配置已被拉取时仍弹）。
3. 上述锚点均为 `void` 返回，hook 时用 `intercept` 直接 `return`（不调用原方法）；`getAdapterKey` 用 `Boolean`/`String` 常量返回 `null`。所有方法需按"形状判据"列校验返回类型/参数类型/`static` 后再挂，名字对了签名不对一律拒绝。
4. 信息流广告只能按资源 id 隐藏：先对目标机做 `uiautomator dump`，统计上表 `id/ad_tag*`、`id/advert_suspend*`、`id/adball*` 的出现次数，只对唯一 id 隐藏；对 DX 卡片这类数据晚到的视图，按视图创建后 1.5/4/8/15s 有限次补隐藏，并在 30s 后复验是否反弹。
5. 校验目标机真实版本：`adb shell dumpsys package com.taobao.idlefish | Select-String versionName`。本报告全部结论只对 **7.28.40 / versionCode 521** 的该 APK 成立。
