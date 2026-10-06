# plasticity asset tool 使用文档

Windows 上的 Plasticity 模型组件库：保存选中对象，浏览组件，在原生视口定位、缩放并确认置入。

当前原生插件实机验证版本为 **Windows / Plasticity 26.1.3**。内部序列化接口依赖 Plasticity 版本，其他版本及跨版本迁移尚未完整验证。

- [文件格式说明](File-Formats.md)：组件包、批量包、数据库、预览与程序发布包有什么区别。
- [导入、导出与备份](Import-and-Export.md)：单个组件、多选、分类及整库导出，迁移和恢复方法。
- [插件安装](Plugin-Installation.md)：自动检测版本与目录，安装、更新及恢复原始入口。
- [项目源码与安装说明](https://github.com/mianxiu/plasticityassettool)

这些文件既可在主仓库的 `docs/wiki/` 阅读，也可作为 GitHub Wiki 页面发布。Wiki 使用独立 Git 仓库；主仓库推送不会自动更新 Wiki。

## 三个容易混淆的概念

**组件包**是用于交换一个组件的 `.patasset`；**组件数据库**是后台实际保存所有组件的 `library/library.sqlite3`；**程序发布包**是包含 EXE、运行时和界面的 Windows ZIP。

导出当前库全部组件适合分享模型；备份整个 `library/` 才能完整保留库、分组、归档状态及预览缓存。
