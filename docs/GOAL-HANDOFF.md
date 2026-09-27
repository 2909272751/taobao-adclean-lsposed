# GOAL-HANDOFF —— 淘系去广告（taobao-adclean-lsposed）

> 单一事实源：任何会话（含全新会话、子代理）只读这一个文件就能接着干，不需要重新摸索。
> 静态逆向的细节在 `docs/RECON-IDLEFISH.md` / `docs/RECON-TAOBAO.md`；
> 每条 hook 的证据在 `docs/ANALYSIS.md`。

## 当前状态

| 项 | 状态 |
|---|---|
| 模块 v0.1.1 构建 | ✅ `app/build.ps1` 全绿，产物 `app/dist/module-v0.1.1.apk`（apksigner verify 通过） |
| 真机安装 + LSPosed 启用 + 作用域 | ✅ 已装、已启用、作用域 = 闲鱼 + 淘宝 |
| 闲鱼 7.28.40 逐特性探针 | ✅ `install_summary splash=matched popup=matched widget=matched sdk=matched`（17 条规则 0 失败） |
| 淘宝 10.66.30 逐特性探针 | ✅ `install_summary splash=matched popup=matched widget=matched sdk=matched`（18 条规则 0 失败） |
| 闸门「真的被调用到」证据 | ✅ 4 条命中行，见下 |
| 设置页 / 开关链路 | ✅ 见下「开关链路实测」：关掉某个特性后目标进程真的报 `result=off`，复位按钮也验证过 |
| 自绘 logo | ✅ `assets/logo/logo-1024.png`；**从构建产物解出的 PNG 与源图逐像素相同**（max delta 0） |
| GitHub 仓库 + Release | ✅ https://github.com/2909272751/taobao-adclean-lsposed （v0.1.0 + v0.1.1） |
| 信息流卡片本体去广告 | ❌ 不可行（两边 base.apk 内都没有渲染期广告判定，已穷举证伪，见 README「已知限制」） |
| 淘宝闪购频道内广告 | ❌ 不在 base.apk（饿了么 ability IDL 侧） |

## 验证证据

设备：RMX5060 / Android 16 / API 36 / LSPosed 1.8.6（API 102）。
日志读法：`adb shell su -c 'sh /data/local/tmp/modlog.sh arm|hits|all'`
（LSPosed 逐模块日志，**不要**用 `logcat -s <模块tag>`，模块日志挂在 `LSPosedFramework` tag 下）。

```
# 1) 逐特性探针（每次冷启动各一行）
(com.taobao.idlefish)[io.github.taobaoadclean,...] [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched
(com.taobao.taobao)[io.github.taobaoadclean,...]  [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched

# 2) 闸门被调用到
(com.taobao.idlefish) blocked id=xy_splash_load_hot
(com.taobao.idlefish) hid id/advert_suspend_img
(com.taobao.taobao)   blocked id=tb_pop_init
(com.taobao.taobao)   blocked id=tb_pop_schedule

# 3) 复现顺序
adb shell am force-stop <目标包>
adb shell monkey -p <目标包> -c android.intent.category.LAUNCHER 1
# 等 15~30s，然后：adb shell su -c 'sh /data/local/tmp/modlog.sh hits'
```

视觉对照：装模块前淘宝首页冷启动浮着「4 张消费券共 … 后到期 · 去使用」倒计时弹窗
（`scratch-recon/ui/tb-t2.png` / `tb-t14.png` / `tb-t20.png`），
装模块后同一入口冷启动首页正常、该弹窗不再出现（`scratch-recon/ui/tb-after-home.png`）。

设置页：`scratch-recon/ui/module-final.png` —— 四行「已布防」+ 每行「对应页面」。

### 开关链路实测（设置页 → RemotePreferences → 目标进程）

```
# 在设置页把「广告 SDK」开关拨到关
sqlite3 .../modules_config.db "select ... from module_configs"
  -> io.github.taobaoadclean / io.github.taobaoadclean_settings / sdk_enabled = ...00   (Java Boolean false)

# 强停闲鱼并冷启动
(com.taobao.idlefish) [schema=1] feature=sdk result=off armed=0 failed=0
(com.taobao.idlefish) [schema=1] install_summary splash=matched popup=matched widget=matched sdk=off

# 点设置页「恢复默认设置（全部开启）」→ module_configs 里该行消失 → 冷启动后
(com.taobao.idlefish) [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched
```

结论：**开关真的能关掉特性，且复位的语义 = 回落到「默认全开」**（`off` 与 `miss` 是两种状态，
前者是用户关的，后者是没找到锚点，UI 文案已区分）。

> 踩坑记录：`uiautomator dump` 在本模块自己的设置页上也报 `could not get idle state`
> —— 因为页面里那个 1 秒一次的刷新 Runnable 让消息队列永远不进 idle。
> 想自动点开关只能靠截图取像素坐标，别指望 uiautomator。

## 已被证伪的假设（省下一个人重复试验）

1. **闲鱼开屏「拦一家 SDK 就够」** —— 不成立。`SplashAdAdapterFactory` 静态注册 5 家
   （mama/toc/beizis/ylh/csj），由服务端 `SplashAdResp.getAdapterKey()` 决定；五家都汇聚到
   `SplashAdShower.showSplashAd(Activity,View,boolean)`。
2. **`com.alimm.xadsdk.business.splashad.*` 是淘宝/闲鱼的开屏总控** —— 不成立。
   淘宝 base.apk 内 `xadsdk` 原始字节命中 **0**；闲鱼里它是 Mama adapter 的内部实现，不是中枢。
3. **`Advert.isShowAdvert()` 是弹窗闸门** —— 不成立，它是开屏显示状态回读，`--callers-of` 返回 0 调用点。
4. **`BootImageInfo#getFromType()` 是开屏闸门** —— 不成立，base.apk 内调用点数为 0。
5. **淘宝开屏类 `BootImageWorkFlow` 不在 base.apk** —— 表面成立、实质证伪：
   原描述符确实不在，但实现被混淆成 `tb.fi2`（内部类名反证身份）。**「类名搜不到」≠「代码不在」。**
6. **信息流广告靠 `isAd`/`adType`/`getItemType` 判定** —— 不成立。淘宝全 dex `method_ids` 无此类方法；
   闲鱼唯一的 `SecondPartyAdHelper.isSecondPartyAdType` 的 4 个调用点全在 DX 卡片**点击**处理器里（埋点）。
7. **`ad_splash_enable` / `ad_enable` 是 Java 侧开关** —— 不成立，全 code_item 无 `const-string` 加载点。
8. **广播收件人可以用 `context.getPackageName()` 拼** —— 不成立，被 hook 的进程里那是目标 App 的包名。
9. **`libs/service-classes.jar` 自带 AIDL 类** —— 不成立，它是编译期精简桩，缺 `IXposedService*`。
10. **`ClassLoader.loadClass("boolean")` 能解析基本类型** —— 不成立，必须显式映射。

## 下一步（按优先级，含前置条件）

1. **验证开关真的能关掉特性**（前置：无）。在设置页关掉「开屏广告」→ 强停闲鱼 → 冷启动 +
   切后台回前台，确认 `blocked id=xy_splash_load_hot` **不再出现**，且 `install_summary` 里 `splash=off`。
2. **给信息流卡片补真实锚点**（前置：能真机 dump 首页推荐 bundle）。
   `tools/recon_bundles.sh` 已备好设备侧枚举脚本；base.apk 内确实没有，必须在
   `/data/data/com.taobao.taobao/files/` 下的动态 dex/jar 里找。
   注意：**不要**用全树遍历兜底（会牺牲流畅度），按 lsposed-module-dev §4.9 的 id 名方案。
3. ~~**`tb.bbd#w(int, IPopData)`**（首页弹窗最深的单点闸门）尚未反编译~~ —— **本条已证伪，作废**。
   `dex_meta.py --methods-of tb.bbd` 显示 `tb.bbd` 是**滚动容器 interface**（`findItemViewByPosition`
   / `scrollToPositionWithOffset` / `getVisiblePositionRange`），**没有 `w` 方法**；
   `tb.e3b` 的字段表显示那个字段的真实类型是 `tb.zbm` 而非 `tb.bbd`。
   弹窗真正的深层闸门是 `tb.e3b#A(int, IPopData) : boolean`，它已由 `tb_pop_trigger_data` 覆盖，无需再加。
   **教训**：子代理给出的「某类是某角色」结论必须用 `--methods-of` / `--fields-of` 复核，
   不要直接写进下一步清单（jadx 的字段类型映射会看花眼）。
4. **闲鱼开屏的视觉验收**（前置：设备上出现真实开屏广告库存）。当前只有 `blocked` 命中行，没有前后截图。
5. **把本轮的三个通用坑回灌到 `skeleton/`**（前置：无）——`resolveOne` 基本类型映射、
   AIDL 三源文件、`Config.MODULE` 拼广播组件。这三条对 `weibo-clean-lsposed` /
   `video-lsposed` / `qq-music-lsposed` 同样成立（它们用的是同一个精简 jar）。✅ 已完成（v0.1.1 轮）。
6. **信息流广告的可行路径只剩一条**：Taobao 的 split APK 已全部盘点（74 个，213MB，
   在 `/data/data/com.taobao.taobao/files/splitcompat/10.66.30/verified-splits/`），
   其中 `FlashSalePluginBType.apk` 只是**闪购骑手地图动画**（AMap+Lottie，37KB），
   不含频道内容；`taobao_android_homepage_remote.apk` / `information_flow_ai.apk` / `tbsearch_remote.apk`
   里也没有任何广告类型判定。**结论：广告项由服务端 JSON + DX 模板决定，本地无判定点。**
   若仍要做，唯一安全的位置是「响应 JSON 解析成 section 模型之前」过滤——按 lsposed-module-dev §4.8，
   过滤点必须早于「按 size 计算布局」；这条需要先定位 infoflow 的响应解析入口（`IContainerDataService`
   的实现 `DosaContainerDataService` 是候选），**并做好「改错了整栏会消失」的回滚准备**。
   本轮判断：风险高于收益，不做。

## 环境备忘

- adb：`C:\Android\adb.exe`；设备 RMX5060（serial 会变，每轮 `adb devices -l` 核对）
- 锁屏密码 258025；`input keyevent 26` 两次 + `input swipe` + `input text 258025` + `input keyevent 66`
- 工具链：`C:\实用软件开发\.android_build_tools\{android-sdk,jdk17}`
- LSPosed 配置库：`/data/adb/lspd/config/modules_config.db`（设备上有 `sqlite3`）。
  **改库后必须重启设备**：lspd 在启动时把模块列表读进内存，直接改库不生效。
  本项目建库 / 查询 SQL：`tools/lspd_enable.sql` / `tools/lspd_compare.sql` / `tools/lspd_query.sql`
- 淘宝首页用 `uiautomator dump` 会一直报 `could not get idle state`（页面从不进入 idle），
  改用 `adb shell dumpsys activity top` 拿 View Hierarchy（里面带 `#7f0aXXXX app:id/xxx`）。
