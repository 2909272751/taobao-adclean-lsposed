# 淘宝 10.66.30 去广告锚点候选

> 目标：`reference-apk/taobao-10.66.30-base.apk`（versionCode 862，`com.taobao.taobao`，77,255,755 bytes，
> 14 个 `classes*.dex`，`dex\n035`，102,873 个 class_def，905,800 条字符串）
> 方法：jadx 1.5.5 单类反编译（`scratch-recon/jadx-tb/*.java`）+ 自建 dex 静态工具链
> （`tools/dex_classdefs.py` 类定义、`tools/dex_callers.py` 全量调用图、`tools/dex_methods.py` 方法名检索）。
> 全部结论均可由 `scratch-recon/callgraph.tsv`（扫描 3,032,227 个调用点，过滤后落盘 1,583,818 条边，
> 189 MB）复核。

## 结论摘要

1. **开屏广告的展示判定主体就在 base.apk 里**，但被混淆成了 `tb.*`：`tb.fi2` **就是**
   `com.taobao.bootimage.arch.flow.bootimage.BootImageWorkFlow`（内部类 `BootImageWorkFlow$2`
   以 `tb.fi2` 为外部实例，`fi2.java:58`；自身日志 TAG 为 `"BootImageWorkFlow"`，`fi2.java:77,121`）。
   链路：`tb.gu`(ActivityLifecycleCallbacks) → `tb.kol`(PageStateService) → `tb.usg`(LinkedSplashManager) →
   **`tb.fi2#a(int, Activity)`（launcherStart，闸门）** → 拦截器数组 `List<tb.m7c>`
   （`BroadcastFlowInterceptor` + `tb.a29`=FatigueWorkFlow）→ `tb.djq`(StateMachine) → `tb.ckc#onStart(...)`
   分发给广告渲染方 `com.taobao.mmad.TopShowBootImage`。
2. **首页弹窗走两套独立框架，都在 base.apk**：(a) 淘宝自研 `com.taobao.infoflow.*pop*`
   （`IPopViewService` / `TbPopViewServiceImpl` / `tb.e3b` HomePopEngine）；
   (b) 阿里 `com.alibaba.poplayer.*`（263 个类）+ 淘宝封装层 `com.taobao.tbpoplayer.*`（131 个类，
   其中 `filter/MtopPopCheckHelper`、`filter/MtopGroupPreCheckManager` 是**服务端准入校验闸门**）。
   **关键结构**：开屏联动小浮层 `SmallPopView` 的父类就是 PopLayer 原生渲染基类
   `com.taobao.tbpoplayer.view.PopCustomNativeBaseView`（`SmallPopView.java:5`）——
   即弹窗与开屏联动浮层**共用 PopLayer 底座**，封堵 PopLayer 可同时覆盖两类现象。
3. **信息流广告卡片的"是不是广告"判定不在 base.apk**：全 dex 的 `method_ids` 里没有任何
   `isAd` / `isAdItem` / `isAdCard` / `adType` / `getItemType` / `getCardType` 方法
   （`scratch-recon/evidence-admethods.txt`，28 条命中全是 `isAdded`/`isAdaptHudScreen` 之类误报）。
   首页推荐流的广告判定随推荐 bundle 下发，或以裸 JSON key 交给 DX 模板，base.apk 内无类型化判定点。
4. **明确"不在 base.apk"的三条链路**：① 阿里妈妈 XAd 开屏 SDK（整个 APK 里 `xadsdk` 字节命中数为 **0**，
   `com.alimama.xadsdk.*`/`com.alimm.xadsdk.*` 全部不存在，只有 `com.taobao.alimama.*` 埋点/CPS 部分）；
   ② 淘宝闪购（无任何 `shangou`/`sg` 类，只有 `me.ele.taobao.flash.sale.ability.ETFlashSaleAbility`
   与 `com.taobao.android.abilityidl.ability.ETFlashSale*` 的饿百 ability IDL）；
   ③ 开屏联动大/小浮层的**触发方**（`BootImageBigPopView`、`SmallPopView` 的构造函数在 base.apk 内
   **无任何调用点**，只有自身内部类互调）。
5. **资源 id 名不在 dex 里**（`--string-re '^id/.*ad'` 命中 0，R 字段已被内联）；已用 apktool 解出
   `public.xml`（23,377 条），拿到了开屏广告层的真实 id（`bootimage_ad_top_layer` 等，见第 5 节）。

---

## 候选锚点表

置信度定义：**高** = 闸门 + "返回空/false/提前 return 即走无广告路径"的调用方证据齐备；
**中** = 闸门成立但缺少完整调用方链；**低** = 只是形状上像，未证实。

### A. 开屏广告 / 启动图（bootimage）

| # | 目标现象 | 类#方法（完整签名） | 形状判据 | 证据（反编译文件:行） | 为什么它是闸门 | 置信度 |
|---|---|---|---|---|---|---|
| A1 | 所有开屏（冷启 1000 + 热启 1001） | `tb.fi2#a(int, android.app.Activity)` → `void`，实例方法，非 static | Hook 后 **直接 return**（不进入原方法体） | `fi2.java:203`（签名）；`fi2.java:219-231`（遍历拦截器）；`fi2.java:237-241`（`if (!z2 && i == 1001) { log("launcherStart: 拦截"); return; }`）；`fi2.java:242-248`（`this.d.u()` / `this.f.a(activity)` / `ckcVar.onStart(...)` 都在 return 之后） | 这是 `BootImageWorkFlow` 的总入口。两处后续动作都在它体内：`:244 this.f.a(activity)`（`tb.djq` 状态机绑定 Activity，开屏真正被拉起的起点）与 `:245-248 ckcVar.onStart(this.d.g(), i)`（把数据分发给 `TopShowBootImage` 等广告渲染方）。提前 return 则两件事都不发生 | 高 |
| A2 | 热启开屏（i==1001） | `tb.m7c#a(int)` → `boolean`（接口，base.apk 内仅 2 个实现） | 返回 `false` | 接口定义 `m7c.java:5-8`；唯一调用点 `fi2.java:226`（`if (!m7cVar.a(i)) { strB = m7cVar.b(); z = false; break; }`）→ 经 `:237` 与 `:238-241` 命中"拦截 return" | 拦截器投票：任一返回 false 即 `z2=false`，热启路径显式 `return`（日志"拦截"） | 高 |
| A3 | 热启开屏（Taobao 自带屏蔽广播） | `com.taobao.bootimage.arch.flow.bootimage.BroadcastFlowInterceptor#a(int)` → `boolean` | 返回 `false`（或直接改字段 `f9516a`） | 签名 `BroadcastFlowInterceptor.java:101-111`（`return this.f9516a`）；广播 `:66` `action == "TBBootImageForbiddenModeBroadcast"`、`:68` `stage == "startForbidden"` → `:76 this.f9516a = false`；`stopForbidden` → `:88 true` | 这是淘宝**自带的开屏屏蔽开关**（远端广播驱动的疲劳/风控降级）。它在 A2 的投票数组里，返回 false 即走 A1 的拦截分支。同时也说明存在一个可用的外部抑制入口 | 高 |
| A4 | 冷启开屏的疲劳度限制 | `tb.a29#a(int)` → `boolean`（`tb.a29` 同时 implements `tb.vxb, tb.m7c`，即 FatigueWorkFlow） | 返回 `false` | `a29.java:5`（类声明）；`a29.java:22-45`：`:27` `boolean zL = l()`，`:32-35` 全局疲劳 → `return false`；`:36-44` `inStartTypeLimit` → `return false`；日志 TAG `"FatigueWorkFlow"`；本地计数模型 `LocalRecordModel.java:8-12`（`localLastShowDayCount` / `coldStartShowDayCount` / `hotStartShowDayCount`） | 第二票拦截器，控制"全局疲劳/启动类型限制"；返回 false 同样进入 A1 的拦截分支（`this.d.G(true, i, name)`）。疲劳数据落在 `LocalRecordModel`（冷/热启分日计数），说明"每日第 N 次开屏"是被本地计数掐掉的 | 高 |
| A5 | 冷启开屏的拦截态落库 | `tb.lh2#G(boolean, int, java.lang.String)` → `void`（`tb.lh2` = `BootImageBizDataFlow`，implements `tb.vxb`） | Hook 传 `z=true` 强制置拦截态（或直接改字段 `v`） | `lh2.java:758-778`，关键 `:765 this.v = z && i == 1000;`；调用方 `fi2.java:237 this.d.G(true ^ z2, i, strB)` | 拦截态只对冷启（1000）生效，是 A1 里"不 return 但也不该展示"的冷启兜底通道。注意 `lh2#g()`（`:501-517`）**不读** `this.v`，即拦截态不通过清空数据列表生效，消费点在状态机侧（未在 base.apk 全面取证） | 中 |
| A6 | 开屏跳过的官方开关 | `tb.kol#a(android.content.Intent)` → `boolean`（`tb.kol` = PageStateService） | 返回 `true`（= 跳过开屏） | `kol.java:44-67`，关键 `:59 boolean zEqualsIgnoreCase = "0".equalsIgnoreCase(data.getQueryParameter("bootImage"));`；调用方 `kol.java:175-179`：`if (a(activity.getIntent())) { ... wziVarE.c("launcher", tb.cg1.SKIP_SPLASH, ...); return; }` | 现成的"跳过开屏"判定：启动 Intent 带 `bootImage=0` 时返回真，调用方立即 return（连流程都不进）。Hook 成恒 true 等于对所有启动跳过开屏 | 高 |
| A7 | 开屏数据请求（省流/断网） | `com.taobao.bootimage.BootImageDataMgr#j()` → `void`（private 语义，实际被 `$b#run` 调用）；`#k()` → `void`（static 单例 `#g()` 取实例） | Hook `j()` 直接 return，或 `k()` 不 postTask | `BootImageDataMgr.java:180-206`（`j()`：`RemoteBusiness.build(...).syncRequest()` 拉开屏数据）；`:208-215`（`k()` = `Coordinator.postTask(new BootImageDataMgr.b())`，`b#run` → `:59-66` 调 `j()`）；`:78-81`（`static g()` 单例） | 断掉服务端开屏素材/配置的获取，是最"上游"的去广告手段（不依赖渲染层）。调用图确认 `#k()` 的唯一调用方是 `kol.java:132`（`tb.kol#c` 即 onActivityStop 里的 `BootImageDataMgr.g().k()`） | 中 |
| A8 | 服务端开屏总开关（Orange 配置） | `tb.oh2#g()` → `void` / `tb.oh2#c(String, String)` → `String`，配置域 `"android_bootimage_client"` | Hook `OrangeConfig#getConfigs("android_bootimage_client")` 返回空 Map | `oh2.java:127-137`（`g()` 读 OrangeConfig 并注册监听）；`:33-40`（`onConfigUpdate` → `BootImageDataMgr.g().b(configs)`）；`:158-183`（`i(rsg)` 写入 `backgroundWaitSeconds`） | 开屏的远端灰度/开关配置域；空配置会让所有 `c(key, default)` 回落默认值。属于"配置面"锚点，需真机确认默认值是否仍放行 | 低 |
| A9 | 首页/启动器位置的开屏（联动） | `tb.usg#a()` → `tb.fi2`；`tb.usg#d()` → `tb.usg`（static 单例） | Hook `a()` 返回 null（调用方需容错） | `usg.java:79-88`（`a()`：`if (this.e == null) this.e = new tb.fi2(); return this.e;`）；`:61-77`（`d()` 双重检查单例）；字段表 `:10-16` 显示 `e` 就是 `tb.fi2` | `LinkedSplashManager` 懒加载 WorkFlow 的唯一入口，`BootImageDataMgr#i()`（`:173`）与 `editionStatusTrigger`（`:712`）都通过它拿 WorkFlow | 中 |
| A10 | 广告渲染方（mmad） | `com.taobao.mmad.TopShowBootImage#onStart(java.util.List<JSONObject>, int)` → `void`（implements `tb.ckc`）；`#getBusinessCode()` → `String`（返回 `"TopShow"`） | 不调用其 `tb.owi#a(list,int,String)` | `TopShowBootImage.java:92-100`（`onStart` → `handleOnStart`）、`:17-30`（`handleOnStart` → `owiVar.a(list,i,str)`）、`:33-35`（`getBusinessCode()` 恒返 `"TopShow"`）、`:47-49`（`instantiate` 建 `tb.owi`） | 光"是否展示"的最后一环：即使数据到了，渲染仍要经 `TopShowBootImage`。它由 `fi2.java:245-248` 的 `ckcVar.onStart` 触发，是 A1 的下游 | 中 |
| A11 | 开屏是否商业广告的分类 | `com.taobao.bootimage.data.BootImageInfo#getFromType()` → `FromType` | 返回 `FromType.UNSUPPORT` | `BootImageInfo.java:129-131`（`from == "commercialAd"` → `COMMERCIALAD`）；枚举 `:100-104`；`bizType` 常量 `:6-16`（`coldStartAd` / `commercialAdNormal` / `commercialAdVideo`） | **【不推荐】**：调用图查询 `BootImageInfo;#getFromType` 在 base.apk 内**调用点为 0**（`scratch-recon/evidence-getfromtype-callers.txt`）。分类结果由 base.apk 之外（flow 引擎/外层模块）消费，单 hook 它不会改变展示。仅作"判据形状"记录 | 已被证伪 |

### B. 首页弹窗 / 营销浮层

| # | 目标现象 | 类#方法（完整签名） | 形状判据 | 证据（反编译文件:行） | 为什么它是闸门 | 置信度 |
|---|---|---|---|---|---|---|
| B1 | 首页弹窗（Popup 数据下发式） | `com.taobao.infoflow.taobao.subservice.biz.pop.TbPopViewServiceImpl#triggerPopShowByPopData(int, com.alibaba.fastjson.JSONObject)` → `boolean` | 返回 `false` | 实现 `TbPopViewServiceImpl.java:740-751`：`:745 IPopData iPopDataA = tb.tgm.a(jSONObject)`，`:746 if (iPopDataA != null && iPopDataA.valid())`，`:747 return this.mPopEngine.A(i, iPopDataA)`，`:749-750` 数据非法即 `return false` | 返回值语义明确：**false = 未展示**（非法数据的官方分支就是 false），调用方是接口 `IPopViewService.java:93`。Hook 恒 false 即所有"数据式"弹窗都不出 | 高 |
| B2 | 首页弹窗（三条其它触发路径） | `TbPopViewServiceImpl#triggerPopShow(int, java.lang.String)` → `void`（`:683-690` → `mPopEngine.y(i,str)`）；`#triggerPopShowByCustomData(JSONObject)` → `void`（`:693-704` → `mPopEngine.z(data)`）；`#triggerPopShowWithDataReset(int,String)` → `void`（`:707-714` → `mPopEngine.B(i,str)`） | Hook 成空实现 | `TbPopViewServiceImpl.java:683-690`、`:693-704`、`:707-714`；接口 `IPopViewService.java:89,91,95` | B1 只覆盖"带 PopData"的路径；这三条（按 id、按自定义 JSON、带重置）是并列入口，必须一起封堵才完整 | 高 |
| B3 | 首页弹层的容器挂载 | `TbPopViewServiceImpl#createContainer(android.content.Context)` → `android.view.ViewGroup`（`:398`）；`#createContainerDefault(Context)`（`:403`）；`#createContainerInPreRender(Context)`（`:423`） | 返回 `null`（**风险高，需容错验证**） | `TbPopViewServiceImpl.java:398-401 / 403-421 / 423-437`；`:403` 与 `:423` 都调用 `:303 scheduleTBHomepagePop(context, frameLayout)`；实际建容器逻辑 `:209-248` | 弹窗必须有宿主容器。不建容器 = 整个 Pop 层不复存在（比逐个拦 trigger 更彻底），但调用方可能 NPE——列为"彻底方案/需验证" | 中 |
| B4 | 首页弹窗引擎（最深层） | `tb.e3b#A(int, com.taobao.homepage.pop.protocol.model.pop.IPopData<?>)` → `boolean`；同类 `#B(int,String)` `:57`、`#v(int,String)` `:207`、`#x(String)` `:225`、`#y(int,String)` `:234`、`#z(IPopData)` `:246` | `A` 返回 false / 其余置空 | `e3b.java:52-55`（`A(...) { return this.c.w(i, iPopData); }`，`c` 字段类型 `tb.bbd`，来自构造器 `:21`）；`e3b.java:57-69`（`B` → `:68 this.c.v(i, str)`）；`:207 / :225 / :234 / :246`（其余四个入口签名） | `tb.e3b` 是 `TbPopViewServiceImpl.mPopEngine` 的真实类型（`TbPopViewServiceImpl.java:15` 字段声明 + 构造器调用图 `TbPopViewServiceImpl;#<init> → Ltb/e3b;#<init>`）。B1/B2 全部下沉到它。真正的展示决策再下一层为 `tb.bbd#w(int, IPopData)`（未反编译，见"下一步"） | 中 |
| B5 | 弹层与 PopLayer 的状态同步（阻止展示） | `com.taobao.infoflow.taobao.subservice.biz.pop.lifecycle.TbPopLayerBroadcastReceiver#onReceive(Context, Intent)` → `void` | Hook 成空实现 | `TbPopLayerBroadcastReceiver.java:79-105`：`:93` `com.alibaba.poplayer.PopLayer.ACTION_OUT_DISPLAY`（`:98` `f10195a=false`）、`:94 ACTION_OUT_DISMISS`（`:95 true`）；`:100-103` 遍历 `Set<tb.e3b>` 逐个 `c(...)`；`:42-51 c()` → `e3bVar.j().s()/t()` | 首页弹层受 PopLayer 的 display/dismiss 广播驱动；屏蔽该接收器可冻结弹层的可见性状态机 | 中 |
| B6 | PopLayer 弹层总闸门（配置白名单） | `com.alibaba.poplayer.config.manager.ConfigManager#findConfigs(com.alibaba.poplayer.trigger.Event, java.util.List<BaseConfigItem>, boolean)` → `tb.pf4`；`#findValidConfigs(Event, List, boolean)` → `tb.pf4`；`#setDirectlyBlackList(java.util.List<String>)` → `void` | `findConfigs/findValidConfigs` 返回 `null`（无配置 = 无弹层），或 `setDirectlyBlackList` 传入全量 | `ConfigManager.java:281`（`findConfigs`）、`:316`（`findValidConfigs`）、`:348`（`setDirectlyBlackList`）、`:357`（`startFetchConfig`）、`:366`（`startLoadConfigs`） | PopLayer 是阿里统一弹层框架（base.apk 内 263 个类）。配置驱动：没有匹配的 config item 就不会产生 `PopRequest`。这是**覆盖面最大**的弹窗闸门（同时管首页弹窗、活动浮层、开屏联动浮层） | 中 |
| B7 | PopLayer 疲劳/计数限制 | `com.alibaba.poplayer.PopLayer#filterFatigue(java.util.List<java.lang.String>)` → `java.util.Map<String,String>`（`:118`）；`#queryNowPopCount()` → `JSONObject`（static，`:102`）；`#isSetup()` → `boolean`（static，`:97`） | `filterFatigue` 返回全量（把全部 key 标记为受限）；`isSetup()` 返回 false | `PopLayer.java:92 getReference()`、`:102 queryNowPopCount()`、`:118 filterFatigue(List)`；`com.alibaba.poplayer.info.frequency.FrequencyManager#k`（`FrequencyManager.java`）参与计数 | 疲劳度是 PopLayer 决定"现在还能不能弹"的直接依据；`isSetup()==false` 时上层代码（`queryNowPopCount`/`filterFatigue`）直接短路 | 中 |
| B8 | PopLayer 触发控制器 | `com.alibaba.poplayer.trigger.InternalTriggerController`（`onActivityStarted/Stopped/Destroyed` 生命周期驱动） | 不注册/不触发 | `InternalTriggerController.java:20`（构造器，入参 `Application`）、`:57-106`（`getActivityKeyCode` / `getCurUri` / `isFragmentKeyCode` 等着陆页识别）、`:212 getCurrentActivity()` | 弹层触发条件（落到哪个页面/URI）由它计算；`ConfigManager#findConfigs` 的 `Event` 参数由它产生 | 低 |
| B9 | 开屏联动小/大浮层视图 | `com.taobao.mmad.linkage.pop.big.BootImageBigPopView#close()` → `void`（`:129`）、`#isShowing()` → `boolean`（`:178`）、构造器 `(Context, tb.nwi)`（`:84`）；`com.taobao.mmad.linkage.pop.small.SmallPopView` 构造器 `(Context)`（`:395`，且 `:5` 显示它 extends `com.taobao.tbpoplayer.view.PopCustomNativeBaseView`） | 不创建实例 / `isShowing()` 恒 false | `BootImageBigPopView.java:84`（构造器）、`:129`（`close()`）、`:178`（`isShowing()`）；`SmallPopView.java:5`（父类 = PopLayer 原生渲染基类）、`:395`（构造器）；`SmallPopView.java:43-178`（内部类 a–f，含 `SmallPopView$a#onSuccess/onFail` 两个 mtop 回调） | 视图本身可关，但**谁 `new` 它们不在 base.apk**：调用图查询 `BootImageBigPopView;#<init>` / `SmallPopView;#<init>` 的调用点数为 0（只有自身内部类互调）。因此只能作为"视图层兜底"锚点；更好的路径是走 B13/B6 的 PopLayer 底座 | 低 |
| B10 | 首页弹窗视图基类 | `com.taobao.homepage.pop.view.popview.BasePopView#getDisplayType()` → `int`（`:236`）、`#checkReRender()` → `boolean`（`:208`）、`#isFinished()` → `boolean`（`:263`）；`#onHandlePopViewEvent(int)`（`:296`） | 让渲染前检查失败 | `BasePopView.java:46`（构造器 `(Context, IPopData, tb.dbd, tb.xq1, tb.e3b)`）、`:208`、`:236`、`:263`、`:296`；子类 `UcpPopView.java:9`（构造器多一个 `tb.esu`，即 UCP 触达类型） | 每个弹层视图的公共基类；`UcpPopView` 是"UCP（统一触达平台）"通道的弹层实现 | 低 |
| B11 | 弹窗的 mtop 准入校验（服务端是否允许弹） | `com.taobao.tbpoplayer.filter.MtopPopCheckHelper#u(com.alibaba.poplayer.layermanager.PopRequest, com.alibaba.fastjson.JSONObject, com.alibaba.poplayer.norm.IUserCheckRequestListener)` → `boolean`（`:205`）；`#e(PopRequest)` → `boolean`（`:243`）；`#m()` → `MtopPopCheckHelper`（static 单例，`:28`） | `u(...)`/`e(...)` 返回 `false`（= 校验不通过） | `MtopPopCheckHelper.java:9`（字段 `Map<PopRequest, Pair<String, MtopBusiness>>`）、`:28`（`static m()`）、`:205`（`u(...)`）、`:243`（`e(...)`）、`:130`（`l(PopRequest)` 组请求参数） | 这是**弹窗展示前的服务端准入校验**：`PopRequest` 逐条送 mtop 校验，返回 boolean 决定放行。`com.taobao.tbpoplayer`（base.apk 内 131 个类）是淘宝对 `com.alibaba.poplayer` 的封装层，`filter/` 子包就是准入过滤器。恒 false 即所有 UCP 弹层都被判"不许弹" | 中 |
| B12 | 弹窗分组预检 | `com.taobao.tbpoplayer.filter.MtopGroupPreCheckManager#o(PopRequest, JSONObject, IUserCheckRequestListener)` → `boolean`（`:503`）；`#j(PopRequest)` → `boolean`（`:270`）；`#i()` → `MtopGroupPreCheckManager`（static 单例，`:201`） | 返回 `false` | `MtopGroupPreCheckManager.java:9`（`ConcurrentMap<String, Map<String, MtopGroupPreCheckManager.a>>`）、`:201`（`static i()`）、`:270`（`j(PopRequest)`）、`:503`（`o(...)`） | 分组（group）粒度的预检，与 B11 是并列的第二道准入。两者都要封堵才算完整 | 中 |
| B13 | PopLayer 原生渲染弹层的基类 | `com.taobao.tbpoplayer.view.PopCustomNativeBaseView#initView(android.content.Context)` → `android.view.View`（abstract，`:24`）；`#shouldReplace(com.alibaba.poplayer.trigger.model.IUCPContext)` → `Pair<Boolean,String>`（`:27`）；`#init(Context, com.alibaba.poplayer.trigger.a)` → `void`（`:34`） | 让 `shouldReplace` 返回 `(true, reason)` / `initView` 返回 null（风险高） | `PopCustomNativeBaseView.java:5`（`abstract class ... extends com.alibaba.poplayer.factory.view.base.PopLayerBaseView<View, com.alibaba.poplayer.trigger.a>`）、`:12 / :24 / :27 / :34` | **关键结构发现**：开屏联动小浮层 `com.taobao.mmad.linkage.pop.small.SmallPopView` 就是它的子类（`SmallPopView.java:5 extends com.taobao.tbpoplayer.view.PopCustomNativeBaseView`，构造器 `:395`）。即**弹窗与开屏联动浮层共用 PopLayer 底座**，封堵 PopLayer 可同时覆盖两类现象 | 中 |

### C. 信息流广告卡片（首页推荐 / 搜索结果）

| # | 目标现象 | 类#方法（完整签名） | 形状判据 | 证据（反编译文件:行） | 为什么它是闸门 | 置信度 |
|---|---|---|---|---|---|---|
| C1 | 广告卡片的公共模型 | `com.taobao.mmad.data.BaseMmAdModel extends com.taobao.bootimage.data.BootImageInfo`：`#getCreativeId()` → `String`（`:51`）、`#getTagType()` → `String`（`:71`）、`#getExposureStg()` → `String`（`:59`）、`#getActionType()` → `int`（`:47`） | 让 `getTagType()` 返回空 / 不构造该模型 | `BaseMmAdModel.java:5`（`extends BootImageInfo`）、`:11 creativeId`、`:15 tagType`、`:17 exposureStg = "0"`、`:18 actionType = -1`；getter `:47-77` | 这是 base.apk 内**唯一**带"广告素材标识"语义的模型（`creativeId`/`tagType`/曝光策略）。但它是开屏/mmad 交互广告用的，**不是推荐流卡片** | 低 |
| C2 | 推荐流卡片适配器 | `com.taobao.infoflow.core.subservice.framework.container.mainfeeds.recycleview.adapter.RecycleViewAdapter`（类存在） | —— | 类定义出现于 `scratch-recon/cd-infoflow-ad.txt:45-48`（class_defs 查询结果）；同包 `model/BaseCardModel`（`:53`）、`model/ErrorCardModel`（`:54`）、`model/LoadingCardModel`（`:55`） | **仅记录**：它是信息流卡片的绑定点，但 base.apk 内**找不到任何"广告卡片"类型判定**。`BaseCardModel` 只有 error/loading 子类，没有 `AdCardModel` | 已被证伪 |
| C3 | 广告字段判定（全表检索） | —— | —— | `scratch-recon/evidence-admethods.txt`：对 102,873 个类的全部 `method_ids` 按 `(isAd\|isAdItem\|isAdCard\|adType\|getAdType\|getItemType\|getCardType\|isAdv\|isAdvert)` 检索，28 条命中全部为 `isAdded()`/`isAdaptHudScreen()`/`isAdvHint()`（搜索框热词）等无关方法 | 结论：**base.apk 内不存在信息流广告判定方法**。判定来自服务端 JSON（可能由 DX 模板消费），或随首页推荐 bundle 运行 | 已被证伪 |

### D. 淘宝闪购 / 阿里妈妈 XAd

| # | 目标现象 | 结果 | 证据 | 置信度 |
|---|---|---|---|---|
| D1 | 淘宝闪购频道广告入口 | **不在 base.apk** | `tools/dex_scan.py --class-re 'shangou\|Shangou\|ShangGou'` → 0 命中；`--class-re 'flash\|Flash\|sg\.\|Sg[A-Z]'` 仅命中 2 组与闪购无关的饿百 ability：`Lme/ele/taobao/flash/sale/ability/ETFlashSaleAbility;`（`scratch-recon/cd-mix.txt:26-28`）与 `Lcom/taobao/android/abilityidl/ability/ETFlashSale*`（`cd-mix.txt:38-57`，均为 `AbsETFlashSaleAbility`/`ETFlashSaleAbilityWrapper` 等 IDL 包装） | 高（否定性结论） |
| D2 | 阿里妈妈 XAd 开屏 SDK | **完全不在 base.apk** | 对 APK 内全部 `classes*.dex` 做原始字节检索 `xadsdk` → **0 命中**；`--class-re 'xadsdk\|alimama\|Alimama'` 共 113 行，描述符列含 `xadsdk` 的行数为 **0**（逐行解析 `scratch-recon/c-xad.txt` 复核），全部是 `com/taobao/alimama/*` 的埋点 CPS/CPC/CPM 上报 + `AlimamaAdvertising`，无 `business.splashad.*`。任务给出的 `com.alimm.xadsdk.business.splashad.SplashAdController` 等 4 个类经 jadx 单类反编译确认 **Input class not found**（`scratch-recon/logs/one-*-SplashAd*.log`） | 高（否定性结论） |
| D3 | 阿里妈妈 Union / P4P | **在 base.apk（但非开屏）** | `Lcom/taobao/muniontaobaosdk/p4p/P4pBusiness;`（已反编译 `P4pBusiness.java`）、`Lcom/taobao/muniontaobaosdk/Munion;`、`Lcom/taobao/munion/taosdk/MunionRequestHelper;` 等，见 `scratch-recon/cd-adpkg.txt` / `cd-adclass.txt` | 中 |

### E. 相关资源 id 名（apktool `public.xml`，`R` 字段已内联故 dex 里查不到）

| 用途 | 资源名 | id | 证据 |
|---|---|---|---|
| 开屏广告最上层容器（**最推荐的形状判据**） | `id/bootimage_ad_top_layer` | `0x7f0a021e` | `scratch-recon/apktool-res/res/values/public.xml:8630` |
| 开屏广告浮层跳过按钮 | `id/bootimage_ad_pop_skip` | `0x7f0a021d` | `public.xml:8629` |
| 开屏交互卡片容器 | `id/bootimage_interact_card_container` | `0x7f0a1b17` | `public.xml:11995` |
| 开屏 DX 交互点击容器 | `id/bootimage_interact_dx_click_container` | `0x7f0a1b1a` | `public.xml:11998` |
| 开屏交互点击容器 | `id/bootimage_interact_click_container` | `0x7f0a021f` | `public.xml:8631` |
| 开屏浮层 Lottie | `id/bootimage_pop_lottie` | `0x7f0a0221` | `public.xml:8633` |
| 开屏大浮层布局 | `layout/bootimage_big_pop` | `0x7f0c00d2` | `public.xml:14231` |
| 开屏交互 DX 模板布局 | `layout/bootimage_interact_dx` | `0x7f0c07ea` | `public.xml:14988` |
| 小程序容器开屏 | `id/tms_splash_container` | `0x7f0a1627` | `public.xml:11394` |
| 广告 logo | `id/layout_ad_logo` | `0x7f0a0a21` | `public.xml:9694` |

> 说明：`tools/dex_scan.py --string-re '^id/.*ad'` 返回 0 条 —— dex 字符串表里**不存在** Android 资源名，
> R 字段常量已被内联为整数。资源名只能从 `resources.arsc` 取，本报告用 `apktool d -s` 得到（未改 dex、未改源码）。

---

## 已反编译的类清单

输出目录：`scratch-recon/jadx-tb/`（jadx 1.5.5，`-r --no-imports --single-class`）。

**com.taobao.* / com.alibaba.*（可读名）**
`BootImageDataMgr`、`BootImageData`、`BootImageInfo`、`GatwaySplashRequest`、
`BroadcastFlowInterceptor`、`MemberHelper`、`LinkedSplashData`、`FeedsData`、
`LocalRecordModel`、`RemoteFatigueDataModel`、
`TopShowBootImage`、`BaseMmAdModel`、`BootImageBigPopView`、`SmallPopView`、
`O2OAdvertising`、`P4pBusiness`、`Munion`、
`IPopViewService`、`IPopConfig`、`IPopData`、`PopConfig`、`PopDataViewModel`、`PopDataViewModel2`、
`TbPopViewServiceImpl`、`TbStickyPopServiceImpl`、`TbPopLayerBroadcastReceiver`、
`BasePopContainer`、`BasePopView`、`UcpPopView`、`HomePopState`、
`PopLayer`、`ConfigManager`、`PopRequest`、`InternalTriggerController`、`FrequencyManager`、
`MtopPopCheckHelper`、`MtopGroupPreCheckManager`、`PopCustomNativeBaseView`、`PopAction`

**tb.*（混淆名，已确认身份）**
| 混淆名 | 真实身份 | 身份证据 |
|---|---|---|
| `tb.fi2` | `com.taobao.bootimage.arch.flow.bootimage.BootImageWorkFlow` | `fi2.java:58`（匿名内部类名为 `BootImageWorkFlow$2`，其构造器入参为 `tb.fi2`）；`fi2.java:77,121`（日志 TAG `"BootImageWorkFlow"`） |
| `tb.usg` | `LinkedSplashManager` | `usg.java:44,138,144,150,158,184,197`（日志 TAG） |
| `tb.kol` | `PageStateService` | `kol.java:36,64,74,87,107,117,120,125,127,131,154,168,171,176,194,203,209,217`（日志 TAG） |
| `tb.lh2` | `BootImageBizDataFlow` | `lh2.java:753,667,673,677,766,777,792`（日志 TAG） |
| `tb.a29` | `FatigueWorkFlow` | `a29.java:33,43,56`（日志 TAG） |
| `tb.oh2` | bootimage 默认配置（TAG `bootimage.default`） | `oh2.java:9,42,63,74,93,111,151,170,175,181` |
| `tb.djq` | `StateMachine` | `djq.java:7`（`private static final String b = "StateMachine"`） |
| `tb.e3b` | 首页弹窗引擎 HomePopEngine | `TbPopViewServiceImpl.java:15`（字段类型）+ 构造器调用图 |
| `tb.bbd` | 弹窗展示控制器（`tb.e3b.c` 字段的类型，`bbd#w(int,IPopData)` 是最终决策） | `e3b.java:21`（构造器入参 `bbdVar`）、`e3b.java:54`（`this.c.w(...)`） |
| `tb.ckc` / `tb.m7c` / `tb.vxb` | 广告渲染回调 / 拦截器 / 数据更新回调接口 | `ckc.java:5-11`、`m7c.java:5-8`、`vxb.java:5-9` |
| `tb.di2`,`tb.ph2`,`tb.qsg`,`tb.wzi`,`tb.cg1` | 开屏数据解析 / 通用工具 / LinkedSplash 容器 / UT 上报 / 常量 | 由 `BootImageDataMgr.java:173-201,265-286` 的调用关系确定 |

未产出（类不存在，非工具失败）：`BootImageWorkFlow`(原名，已混淆为 `tb.fi2`)、`BootImageWorkFlowManager`、
`BootImageInfoManager`、`SplashAdController`、`SplashAdModel`、`SplashAdCacheManager`、`SplashAdRequestHelper`。
已知流程瑕疵：jadx `--single-class-output` 按**叶子类名**落盘，不同包下的同名类会互相覆盖 ——
`PopDataViewModel.java` 与 `PopDataViewModel2.java` 内容完全相同（6,167 bytes），即为一次覆盖的副产物；
引用这两个类时应以包名为准，不要只看文件名。

---

## 已被证伪 / 不成立的猜测

1. **`com.alimm.xadsdk.business.splashad.*` 存在于 base.apk** —— 证伪。
   APK 内 `xadsdk` 原始字节命中数 0；`--class-re 'xadsdk'` 0 命中；jadx 单类反编译报
   `Input class not found`（`scratch-recon/logs/one-0-SplashAdController.log` 等 4 个）。
   线索里"dex 里已确认存在这些类"对 `com.taobao.*` 那批成立，对 `com.alimm.xadsdk.*` 不成立。
2. **`com.taobao.bootimage.arch.flow.bootimage.BootImageWorkFlow` 不在 base.apk（任务给的类名查不到）** —— 表面成立、实质证伪。
   该类的**原描述符确实不在**任何 dex 的 class_def 里（`scratch-recon/tb-classdefs.txt` 中只有 `BootImageWorkFlow$2`），
   但它的**实现就在 base.apk**，只是被混淆重命名为 `tb.fi2`。jadx 找不到是因为只认现描述符。
   **教训：base.apk 里"类名搜不到"不等于"代码不在"，必须走调用图/内部类反查。**
3. **`BootImageInfo#getFromType()` 是开屏广告闸门** —— 证伪。
   base.apk 内调用点数为 0（`scratch-recon/evidence-getfromtype-callers.txt`），返回值由外部消费。
   同理 `bizType`/`FromType.COMMERCIALAD` 都只是"数据标注"，不是决策点。
4. **信息流广告卡片靠 `isAd`/`itemType`/`cardType` 方法判定** —— 证伪。
   全 dex `method_ids` 无此类方法（`scratch-recon/evidence-admethods.txt`）；
   调用图中匹配 `#(isAd|getItemType|getCardType|adType)\(` 的调用点为 0。
5. **淘宝闪购 (`shangou`/`sg`/`flash`) 广告入口在 base.apk** —— 证伪（详见 D1）。
6. **资源 id 名可以从 dex 字符串表搜到** —— 证伪。
   `--string-re '^id/.*ad'` 0 命中；dex 内不存在 `id/xxx` 形态的资源名。
7. **开屏联动大/小浮层（`BootImageBigPopView`/`SmallPopView`）的触发方在 base.apk** —— 证伪。
   两个构造器的调用点数为 0，只有自身内部类互调；触发方在 base.apk 之外。
8. **`tb.lh2#g()` 会因为拦截态返回空列表** —— 证伪。
   `lh2.java:501-517` 未读 `this.v`，直接聚合所有列表。拦截态不是通过清空数据生效的
   （`lh2#G` 的 `:765 this.v = z && i == 1000` 只置字段，消费点在 base.apk 未定位）。

---

## 下一步建议

1. **优先实测 A1 + A3 组合**（成本最低、语义最干净）：
   hook `tb.fi2#a(int, android.app.Activity)` 直接 return；同时 hook
   `BroadcastFlowInterceptor#a(int)` 恒 false。前者断掉冷/热启动两条路径，后者覆盖热启显式拦截分支。
   验证点：冷启（`am force-stop` 后启动）和热启（退到后台再回前台）分别截图确认无开屏图/无广告。
2. **拿到 `tb.bbd#w(int, IPopData)` 的具体实现**（B4 的下一层，唯一未反编译的弹窗决策点）：
   已确认它在 base.apk（`e3b.java:54 this.c.w(i, iPopData)` 有调用点），是首页弹窗最深的单点闸门。
3. **弹窗若要"一刀切"，优先试 B11+B12**（`MtopPopCheckHelper#u/#e` + `MtopGroupPreCheckManager#o/#j`
   全部恒 false）**再叠 B1/B2 的 trigger 封堵**。这两处是 base.apk 内的服务端准入判定，覆盖面比逐个
   trigger 更全；且它们和 `SmallPopView`（开屏联动小浮层）共用 PopLayer 底座，能顺带压掉联动浮层。
4. **补 PopLayer 侧证据**（B6/B7 从"中"提到"高"）：反编译 `com.alibaba.poplayer.trigger.BaseTriggerService`、
   `layermanager/a`、`layermanager/d`，确认"`findConfigs` 返回 null → 不产生 `PopRequest`"这条链的调用方。
5. **确认 `tb.lh2.v`（拦截态）的消费点**：对 `lh2` 实例的字段读只能靠 smali/指令级扫描，
   建议对 `scratch-recon/jadx-tb/zh2.java`（状态机初态）与 `tb.xiq` 逐方法核对 `v` 的读取。
6. **不在这台机器上重复的弯路**：不要再花时间找 `xadsdk`、`shangou`、信息流 `isAd` 判定 ——
   三者在 base.apk 内已被上限穷举证伪。
7. 若要动**信息流广告**，必须在真机上 dump 首页推荐 bundle（`/data/data/com.taobao.taobao/files/` 下的
   动态 dex/jar，用 `tools/recon_bundles.sh` 的设备侧脚本枚举），base.apk 内无对应代码。

### 复核用命令（全部只读，可重跑）

```powershell
# 类定义全表（决定"某个类究竟在不在 base.apk"）
python tools\dex_classdefs.py reference-apk\taobao-10.66.30-base.apk scratch-recon\tb-classdefs.txt
python tools\cd_grep.py scratch-recon\tb-classdefs.txt 'BootImage|bootimage'

# 全量调用图（决定"闸门的调用方是谁"）
python tools\dex_callers.py reference-apk\taobao-10.66.30-base.apk --dump scratch-recon\callgraph.tsv --limit 0 `
  --skip-callee '^L(android|java|javax|kotlin|kotlinx|org|sun|dalvik|libcore|com/google|com/facebook|com/squareup|okhttp3|okio|retrofit2|mtopsdk|com/alibaba/fastjson)/'
python tools\cg.py scratch-recon\callgraph.tsv callers 'BootImageInfo;#getFromType'
python tools\cg.py scratch-recon\callgraph.tsv callers 'Ltb/m7c;#a'

# 方法名穷举（决定"某类判定方法到底存不存在"）
python tools\dex_methods.py reference-apk\taobao-10.66.30-base.apk '(isAd|isItem|adType|getItemType)'

# 弹层框架普查（PopLayer / tbpoplayer 全量类名）
python tools\cd_grep.py scratch-recon\tb-classdefs.txt 'poplayer|PopLayer'
python tools\cd_grep.py scratch-recon\tb-classdefs.txt 'taobao/tbpoplayer'
```

工具本身在本轮被修过三个真 bug：① `class_idx` 是 `type_ids` 索引而非 `string_ids` 索引
（导致第一版类定义全表是乱码，曾误报出 `HomeBootImage`/`CreateViewState` 等**并不存在**的类）；
② `proto_id_item` 是 12 字节而非 8（导致方法签名解析全错）；
③ `direct_methods` 与 `virtual_methods` 是两条独立的 `method_idx_diff` 累加链（导致虚方法名错位）。
修完后已用 jadx 输出交叉验证：`BootImageDataMgr` 的调用图方法名 `b/c/d/e/f/g/h/i/j/k` 与
`BootImageDataMgr.java` 完全一致。**这三条 bug 的教训是：反向"证明某类不存在"之前，必须先验证解析器本身。**
