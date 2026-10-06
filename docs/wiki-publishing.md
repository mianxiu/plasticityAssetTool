# GitHub Wiki 发布说明

文档源文件在 `docs/wiki/`，主仓库 README 已提供阅读入口。Wiki 是独立 Git 仓库，不能靠推送主仓库分支自动发布。

## 当前发布状态

2026-10-06 已发布到 [GitHub Wiki](https://github.com/mianxiu/plasticityassettool/wiki)：首页、安装、保存置入、基点预览、布尔组、导入备份、控制中心、文件格式、常见问题和开发指南，共 10 个正文页面及侧栏。README 的文档入口已改为实际 Wiki 链接。

`docs/wiki/` 是主仓库中可审核、可追踪的文档源文件。Wiki 使用独立 Git 仓库，更新这些源文件后仍需同步发布；保留 Wiki 中其他已有页面。

## 同步步骤

1. 在仓库 Settings → General → Features 启用 Wiki；若 GitHub 提示升级，需先满足私有仓库的功能条件。
2. 在仓库 Wiki 页面创建首个 `Home` 页面。GitHub 要求先创建页面，才能克隆 Wiki Git 仓库。[创建与编辑 Wiki](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages)
3. 克隆 `https://github.com/mianxiu/plasticityassettool.wiki.git` 到单独目录。
4. 将 `docs/wiki/` 中的页面和 `_Sidebar.md` 复制到 Wiki 仓库，保留其他已有页面。
5. 将文档内部的本地页面链接改为无 `.md` 后缀的 Wiki 页面名；主仓库源文件保留 `.md` 相对链接。
6. 在 Wiki 仓库提交并推送，检查首页、侧栏及页面链接。

也可直接阅读主仓库中的文档源文件。此流程不需要改变仓库可见性，也不上传模型库、运行缓存或安装备份。
