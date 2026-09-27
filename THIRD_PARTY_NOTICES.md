# 第三方组件与来源

本模块的**业务代码**（`app/src/io/github/taobaoadclean/`）为本项目原创，
logo（`assets/logo/`、`app/res/drawable-nodpi/`）由 `tools/make_logo.py` 用几何图元绘制，亦为原创。

以下文件是**框架级**代码（libxposed API 与框架服务通道），与目标 App 无关，随模块一起分发：

| 文件 | 来源 | 许可 |
|---|---|---|
| `app/stub-src/io/github/libxposed/api/*.java` | [libxposed API](https://github.com/LibXposed/libxposed-api)（`io.github.libxposed:api`）compile-only 桩 | Apache-2.0 |
| `app/libs/service-classes.jar` | 同上，`service` 模块的 compile-only 精简桩 | Apache-2.0 |
| `app/src/io/github/libxposed/service/IXposedService.java`<br>`app/src/io/github/libxposed/service/IHotReloadCallback.java`<br>`app/src/io/github/libxposed/service/IXposedScopeCallback.java` | 由 `IXposedService.aidl` / `IHotReloadCallback.aidl` / `IXposedScopeCallback.aidl` 经 Android SDK `aidl` 生成的 Java（同属 libxposed API 的 service 模块） | Apache-2.0 |

> 说明：`service-classes.jar` 是编译期精简桩，**不含** AIDL 生成的
> `IXposedService` / `IHotReloadCallback` / `IXposedScopeCallback` 系列类。
> 缺了它们在运行期会让 `XposedServiceHelper.onBinderReceived` 抛
> `NoClassDefFoundError`（被 `catch(Throwable)` 吞掉，表现为设置页永远显示
> 「LSPosed 配置服务未连接」）。因此本项目把这三个 AIDL 源文件一并放进
> `app/src/io/github/libxposed/service/` 参与编译。

本项目**不包含**任何来自闲鱼 / 淘宝 App 的代码、资源或反编译产物。
`reference-apk/`、`scratch-recon/`（逆向中间产物）已在 `.gitignore` 中排除，不随仓库分发。
