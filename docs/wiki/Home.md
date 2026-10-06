# Plasticity Asset Tool 使用文档

Windows 上的 Plasticity 本地模型组件库。当前实机验证版本为 **Plasticity 26.1.3**。本文档对应当前源码，旧发布包可能尚未包含最新功能。

## 使用指南

- [安装、更新与恢复](Plugin-Installation.md)
- [保存与原生置入](Saving-and-Placement.md)
- [3D 预览、基点与缩略图](Preview-and-Base-Point.md)
- [布尔模式与连续布尔组](Boolean-Modes.md)
- [导入、导出与整库备份](Import-and-Export.md)
- [面板与控制中心](Control-Center.md)
- [文件格式](File-Formats.md)
- [常见问题](FAQ.md)
- [源码运行与界面更新](Development.md)

## 演示与项目资料

- [操作演示动画](https://github.com/mianxiu/plasticityassettool#操作演示)
- [许可证说明](../Licensing.md)
- [第三方声明与使用风险](../../DISCLAIMER.md)
- [项目源码](https://github.com/mianxiu/plasticityassettool)

## 组件交换与整库恢复

`.patasset` 交换单个组件，组件 ZIP 批量交换组件；控制中心的整库备份保存全部库、分组和组件状态，恢复会替换当前库数据。两种 ZIP 使用不同入口，详见导入与备份指南。
