# 淘系去广告 v0.1.0

首个版本。针对 **闲鱼 7.28.40（521）** 与 **淘宝 10.66.30（862）**，
逐特性独立探测、逐特性可关，未命中时对目标 App **零影响**。

## 功能

- **开屏广告**（冷启动 / 切回前台 / 路由唤起）
- **弹窗广告**（首页浮层 / 活动弹窗 / 开屏联动浮层）
- **悬浮广告与广告球**（按资源 id 名隐藏独立浮层容器）
- **广告 SDK 初始化与预加载**（省电省流量）

四项默认开启。

## 实测（RMX5060 / Android 16 / LSPosed 1.8.6）

```
(com.taobao.idlefish) [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched
(com.taobao.taobao)   [schema=1] install_summary splash=matched popup=matched widget=matched sdk=matched
```
共 32 条规则全部布防成功、0 失败。闸门命中行：
```
blocked id=xy_splash_load_hot     (闲鱼 热启动开屏)
hid id/advert_suspend_img         (闲鱼 首页悬浮广告位)
blocked id=tb_pop_init            (淘宝 首页弹窗预渲染初始化)
blocked id=tb_pop_schedule        (淘宝 首页弹窗装配入口)
```

## 校验

- APK：`taobao-adclean-v0.1.0.apk`
- SHA-256 见 Release 附件旁的 `SHA256SUMS.txt`
- 签名：本地测试密钥（`CN=LocalTest`），换签名必须卸载重装（会清空模块设置）

## 已知限制（不粉饰）

1. **信息流卡片本体没有去掉**：两边 base.apk 内都不存在渲染期广告判定
   （首页推荐流由服务端 DynamicX 模板渲染，模板运行时从 OSS 下载）。
   本版本只清理有独立容器的浮层广告位。
2. **淘宝闪购频道内的广告不覆盖**：该频道代码不在 `com.taobao.taobao` 的 base.apk 内。
3. **闲鱼开屏只拿到闸门命中行，没拿到前后对比截图**：本机当前没有开屏广告库存。

## 从源码构建

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\app\build.ps1
```
