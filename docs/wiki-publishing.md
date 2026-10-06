# GitHub Wiki 发布说明

文档源文件在 `docs/wiki/`，主仓库 README 已提供阅读入口。Wiki 是独立 Git 仓库，不能靠推送主仓库分支自动发布。

## 当前发布状态

2026-10-06 检查：主仓库已公开，当前账号有管理员及推送权限，`has_wiki=true`。Wiki Git 地址仍返回 `Repository not found`，尚需在 GitHub 网页创建首个 `Home` 页面。详细文档现已按主题整理到 `docs/wiki/`，README 只保留特色功能、演示与文档入口。

创建首页后即可同步；首次创建需要已登录的 GitHub 浏览器。主仓库文档入口保持可用，Wiki 初始化与推送完成后再将 README 入口切换到实际 Wiki 地址。

## 同步步骤

1. 在仓库 Settings → General → Features 启用 Wiki；若 GitHub 提示升级，需先满足私有仓库的功能条件。
2. 在仓库 Wiki 页面创建首个 `Home` 页面。GitHub 要求先创建页面，才能克隆 Wiki Git 仓库。[创建与编辑 Wiki](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages)
3. 克隆 `https://github.com/mianxiu/plasticityassettool.wiki.git` 到单独目录。
4. 将 `docs/wiki/` 中的页面和 `_Sidebar.md` 复制到 Wiki 仓库，保留其他已有页面。
5. 将文档内部的本地页面链接改为无 `.md` 后缀的 Wiki 页面名；主仓库源文件保留 `.md` 相对链接。
6. 在 Wiki 仓库提交并推送，检查首页、侧栏及页面链接。

Wiki 初始化前可直接阅读主仓库中的文档，内容与准备发布到 Wiki 的版本一致。此流程不需要改变仓库可见性，也不上传模型库、运行缓存或安装备份。
