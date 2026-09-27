# 逆向证据表（docs/ANALYSIS.md）

> 每条规则都注明**反编译文件:行**与**为什么它是闸门**。
> 数字前缀 `tb.` / `xy.` 与 `MainHook.java` 里的 hook id 一一对应。
> 详细报告见 `RECON-IDLEFISH.md`（闲鱼 7.28.40 / 521）与 `RECON-TAOBAO.md`（淘宝 10.66.30 / 862）。

## 通用纪律

- **严格签名校验**：参数个数 / 参数类型 / 返回类型全部核对；**歧义（多个同形状候选）即失败**，
  绝不「随便挑一个」——挑错的后果是行为异常，比不生效更糟。
- **fail-open**：任何一条规则装不上只记 `rule unavailable`，其余规则继续；全部失败时目标 App 行为与未装模块完全一致。
- **intercept 内零分配、零反射、零日志**：命中只做一次 CAS 打点。
- 只 hook 一次性闸门，无高频路径。

## 一、闲鱼（com.taobao.idlefish 7.28.40 / versionCode 521）

### 开屏广告（feature = splash，5 条）

| hook id | 类#方法 | 形状判据 | 证据 | 为什么它是闸门 |
|---|---|---|---|---|
| `xy_splash_showmaybe` | `com.taobao.fleamarket.advert.Advert#showMaybe(Activity)` | `(Activity) → void`，static | `Advert.java:18-33`；调用者 `MainPageJumpWorkflow.jump()` | 冷启动开屏唯一入口。空实现后**连遮罩和广告请求都不会发生**（`:28` 判 `splashCoverOn()` 之后才投递） |
| `xy_splash_load` | `SplashAdController#loadSplashAd(Activity)` | `(Activity) → void`，public final 实例 | `SplashAdController.java:342-355`（`:346`/`:351` 调 `showCover`） | 遮罩与广告请求的共同起点 |
| `xy_splash_load_hot` | `SplashAdController#loadSplashAdHotStart()` | `() → void` | `SplashAdController.java:357-382`；唯一调用者 `SplashAdController$1.onAppForeground()` | 切回前台开屏的唯一入口 |
| `xy_splash_load_toc` | `SplashAdController#loadToCSplashAd()` | `() → void` | `SplashAdController.java:384-386`；调用者 `RouterInterrupterSplashAd.checkInterrupt` | 路由唤起时强制走开屏的第三条入口 |
| `xy_splash_shower` | `SplashAdShower#showSplashAd(Activity, View, boolean)` | `(Activity, View, Z) → void`，public final | `SplashAdShower.java:89`；五家 DSP 调用点：Csj:129 / Ylh:137 / Beizis:128 / Mama:38 / ToC:71 | 闲鱼开屏**五路 DSP（mama/toc/beizis/ylh/csj）唯一的共同渲染出口**，兜底用 |

### 弹窗广告（feature = popup，3 条）

| hook id | 类#方法 | 形状判据 | 证据 | 为什么它是闸门 |
|---|---|---|---|---|
| `xy_pop_request_and_show` | `PopWindowController#requestAndShowPopWindow(long)` | `(J) → void` | `PopWindowController.java:283-300`；三个触发源 `MainPageJumpWorkflow.java:256/:269`、`PopMainWorkflow.java:81` | 登录成功 / 新人引导 / 主容器 idle 三个触发源的**统一入口** |
| `xy_pop_handle` | `PopWindowController#doHandleShowPopWindow()` | `() → void`，包级私有 final | `PopWindowController.java:220-235`（`:224` 读 `popWindowConfig.pop`、`:226` 判空、`:230` 才 `showPopWindow`） | 真正决定「弹不弹」的那一步 |
| `xy_pop_config_request` | `PopWindowRequestController#request(ContextWrapper, boolean, ApiCallBack)` | `(ContextWrapper, Z, ApiCallBack) → void` | `PopWindowRequestController.java:53`；唯一调用者 `PopWindowController` 的 lambda | 弹窗配置的 MTop 拉取点，空实现后**连这次网络请求都省掉** |

### 悬浮广告位（feature = widget，1 条）

| hook id | 挂点 | 隐藏的 id 名 | 证据 |
|---|---|---|---|
| `widget_ids` | `Activity#onResume`（每个 Activity 只在 Resumed 时扫一次，非轮询） | `advert_suspend_layout` / `advert_suspend_stub` / `advert_suspend_img` / `adball_layout` / `adball` | 资源名来自 `tools/arsc_scan.py` 解析闲鱼 `resources.arsc`（0x7f0900e1 / 0x7f0900e2 / 0x7f0900e0 / 0x7f0900d6 / 0x7f0900d4） |

- 数据晚到的浮层会「复现」：视图创建后按 2s / 6s / 12s **固定次数**补隐藏，不是轮询。
- **找不到 id 就什么都不做**；`id/advert_suspend_img` 本机实测命中。

### 广告 SDK（feature = sdk，5 条）

| hook id | 类#方法 | 形状判据 | 证据 | 为什么它是闸门 |
|---|---|---|---|---|
| `xy_sdk_csj_cfg` | `NewSplashAdOrange#thirdCsjOn()` | `() → Z`，static | `NewSplashAdOrange.java:273`；`SplashAdCsjAdapter.java:28` 硬短路 `if (!thirdCsjOn()) { ...; return; }` | 闲鱼**自带的「关掉穿山甲开屏」开关**，非混淆、跨版本最稳 |
| `xy_sdk_ylh_cfg` | `NewSplashAdOrange#thirdYlhOn()` | `() → Z`，static | `NewSplashAdOrange.java:280`；`SplashAdYlhAdapter.java:25` | 同上（优量汇/GDT） |
| `xy_sdk_beizi_cfg` | `NewSplashAdOrange#thirdAdPlusOn()` | `() → Z`，static | `NewSplashAdOrange.java:252`；`SplashAdBeizisAdapter.java:30` | 同上（BeiZi） |
| `xy_sdk_csj_init` | `ThirdSdkUtil#initCsjSdk(SdkInitListener)` | `(SdkInitListener) → void`，static | `ThirdSdkUtil.java:11`（`:24 TTAdSdk.init`、`:25 TTAdSdk.start`） | 穿山甲 SDK 唯一启动入口 |
| `xy_sdk_ylh_init` | `ThirdSdkUtil#initYlhSdk(SdkInitListener)` | `(SdkInitListener) → void`，static | `ThirdSdkUtil.java:45`（`:59 GDTAdSdk.initWithoutStart`、`:60 GDTAdSdk.start`） | 优量汇 SDK 唯一启动入口 |

## 二、淘宝（com.taobao.taobao 10.66.30 / versionCode 862）

### 开屏广告（feature = splash，5 条）

| hook id | 类#方法 | 形状判据 | 证据 | 为什么它是闸门 |
|---|---|---|---|---|
| `tb_bootimage_gate` | `tb.fi2#a(int, Activity)` | `(int, Activity) → void` | `fi2.java:203`（签名）、`:219-231`（拦截器投票）、`:237-241`（命中「拦截 return」）、`:242-248`（`d.u()` / `f.a(activity)` / `ckcVar.onStart(...)` 全在 return 之后） | `tb.fi2` **就是** `BootImageWorkFlow`（内部类 `BootImageWorkFlow$2` 以 `tb.fi2` 为外部实例，`fi2.java:58`；日志 TAG `BootImageWorkFlow`，`fi2.java:77`）。**开屏总闸门**：提前 return 则拉起与分发都不发生 |
| `tb_bootimage_forbidden` | `BroadcastFlowInterceptor#a(int)` | `(int) → Z` | `BroadcastFlowInterceptor.java:101-111`（返回字段 `f9516a`）；`:66/:68` 收 `TBBootImageForbiddenModeBroadcast` + `startForbidden` → `:76 false` | 淘宝**自带的开屏抑制开关**，是 `tb.fi2` 投票数组的成员（`fi2.java:226` 是本 App 内 `tb.m7c#a` 的唯一调用点） |
| `tb_page_skip_splash` | `tb.kol#a(Intent)` | `(Intent) → Z` | `kol.java:44-67`（`:59 "0".equalsIgnoreCase(data.getQueryParameter("bootImage"))`）；调用方 `kol.java:175-179` 返回真即 `return`，记 `SKIP_SPLASH` | 官方「跳过开屏」判定；`tb.kol` = `PageStateService`。恒 true = 对所有启动跳过开屏 |
| `tb_topshow_onstart` | `com.taobao.mmad.TopShowBootImage#onStart(List, int)` | `(List, int) → void` | `TopShowBootImage.java:92-100` → `handleOnStart` → `:28 owiVar.a(list, i, str)` | 广告渲染方（mmad TopShow）。数据到了也不渲染 |
| `tb_bootimage_receive` | `com.taobao.bootimage.BootImageDataMgr#i(JSONObject)` | `(JSONObject) → void` | `BootImageDataMgr.java:140-178`（`notifyReceive` 把开屏数据推进 `tb.usg.d().b()`） | 开屏素材/配置的接收点（渲染层之外的兜底） |

### 弹窗广告（feature = popup，10 条）

| hook id | 类#方法 | 形状判据 | 证据 |
|---|---|---|---|
| `tb_pop_schedule` | `TbPopViewServiceImpl#scheduleTBHomepagePop(Context, FrameLayout)` | `(Context, FrameLayout) → void`，private | `TbPopViewServiceImpl.java:303-315`；被 `createContainerDefault:403` 与 `createContainerInPreRender:423` 调用 |
| `tb_pop_init` | `TbPopViewServiceImpl#checkInitPop(Context)` | `(Context) → void`，private | `TbPopViewServiceImpl.java:190-205`（建 window invoker + `mPopEngine.j().j(activity)`） |
| `tb_pop_trigger_data` | `TbPopViewServiceImpl#triggerPopShowByPopData(int, JSONObject)` | `(int, JSONObject) → Z` | `TbPopViewServiceImpl.java:740-751`：`:747 return mPopEngine.A(...)`，`:749-750` 数据非法即 `return false` —— **false = 未展示**是官方分支 |
| `tb_pop_trigger_id` | `TbPopViewServiceImpl#triggerPopShow(int, String)` | `(int, String) → void` | `:683-690` → `mPopEngine.y(i, str)` |
| `tb_pop_trigger_custom` | `TbPopViewServiceImpl#triggerPopShowByCustomData(JSONObject)` | `(JSONObject) → void` | `:693-704` → `mPopEngine.z(data)` |
| `tb_pop_trigger_reset` | `TbPopViewServiceImpl#triggerPopShowWithDataReset(int, String)` | `(int, String) → void` | `:707-714` → `mPopEngine.B(i, str)` |
| `tb_pop_check_u` | `MtopPopCheckHelper#u(PopRequest, JSONObject, IUserCheckRequestListener)` | `(PopRequest, JSONObject, IUserCheckRequestListener) → Z` | `MtopPopCheckHelper.java:205`；`:9` 字段 `Map<PopRequest, Pair<String, MtopBusiness>>`；`:28` static 单例 |
| `tb_pop_check_e` | `MtopPopCheckHelper#e(PopRequest)` | `(PopRequest) → Z` | `MtopPopCheckHelper.java:243` |
| `tb_pop_group_o` | `MtopGroupPreCheckManager#o(PopRequest, JSONObject, IUserCheckRequestListener)` | 同上三参 → `Z` | `MtopGroupPreCheckManager.java:503`；`:201` static 单例 |
| `tb_pop_group_j` | `MtopGroupPreCheckManager#j(PopRequest)` | `(PopRequest) → Z` | `MtopGroupPreCheckManager.java:270` |

> 后四条是 **PopLayer 底座的服务端准入校验**。关键结构：开屏联动小浮层
> `com.taobao.mmad.linkage.pop.small.SmallPopView` 的父类就是 PopLayer 原生渲染基类
> `com.taobao.tbpoplayer.view.PopCustomNativeBaseView`（`SmallPopView.java:5`），
> 所以封堵 PopLayer 同时压掉「弹窗」和「开屏联动浮层」两类现象。

### 悬浮/开屏浮层（feature = widget，1 条）

| hook id | 挂点 | 隐藏的 id 名 | 证据 |
|---|---|---|---|
| `widget_ids` | `Activity#onResume` | `bootimage_ad_top_layer`(0x7f0a021e) / `bootimage_ad_pop_skip`(0x7f0a021d) / `bootimage_interact_card_container`(0x7f0a1b17) | `scratch-recon/apktool-res/res/values/public.xml:8630/8629/11995` |

### 广告 SDK / 预加载（feature = sdk，2 条）

| hook id | 类#方法 | 形状判据 | 证据 |
|---|---|---|---|
| `tb_bootimage_prefetch` | `BootImageDataMgr#j()` | `() → void`，public final | `BootImageDataMgr.java:180-206`（`RemoteBusiness.build(...).syncRequest()` 拉开屏数据） |
| `tb_bootimage_post_task` | `BootImageDataMgr#k()` | `() → void` | `BootImageDataMgr.java:208-215`（`Coordinator.postTask(new b())`，`b#run` → `j()`）；唯一调用方 `kol.java:132` |

> 淘宝 base.apk 内**没有**第三方广告 SDK 的初始化锚点（`xadsdk` 全 APK 字节命中 0，已穷举证伪），
> 所以这一项在淘宝侧退化为「断掉开屏数据的后台预加载」，语义与开关文案一致。

## 三、这条链路上踩过的坑（同样会坑到下一个模块）

| 现象 | 真因 | 修法 |
|---|---|---|
| 规则明明存在却报 `ClassNotFoundException: Didn't find class "boolean"` | 参数形状用 `ClassLoader.loadClass("boolean"/"long")` 解析**基本类型**，必然失败 | `resolveOne()` 里把 9 个基本类型显式映射成 `boolean.class` 等 |
| 设置页永远显示「LSPosed 配置服务未连接」 | `libs/service-classes.jar` 是**编译期精简桩**，缺 AIDL 生成的 `IXposedService` / `$Stub` / `IHotReloadCallback` / `IXposedScopeCallback`；运行期 `XposedServiceHelper.onBinderReceived` 抛 `NoClassDefFoundError`，被 `catch(Throwable)` 吞掉只留一行 `E XposedServiceHelper` | 把这三个 AIDL 源文件放进 `app/src/io/github/libxposed/service/`（与 `stub-src` 同属框架级代码） |
| 设置页收不到任何适配报告，目标进程无任何报错 | 广播收件人写成了 `reportContext.getPackageName()`——在目标进程里那是**目标 App 的包名**，拼出的组件不存在，广播被静默丢弃 | 用 `Config.MODULE` 常量拼 `ComponentName` |
| 设置页在目标 App 启动前没打开过 → 看不到适配状态 | 模块 App 此时处于 stopped 状态，显式广播唤不起它 | 先打开一次设置页；页面本身也有对应提示文案 |
