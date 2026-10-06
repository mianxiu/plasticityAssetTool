# GitHub Wiki 发布说明

文档源文件在 `docs/wiki/`，主仓库 README 已提供阅读入口。Wiki 是独立 Git 仓库，不能靠推送主仓库分支自动发布。

## 当前检查结果

2026-10-05 检查 `mianxiu/plasticityassettool`：仓库为私有仓库，当前账号有管理员及推送权限，但 `has_wiki=false`。调用仓库设置接口请求启用 Wiki 后，再次读取仍为 `false`；Wiki Git 地址返回 `Repository not found`。所以本次文档发布到主仓库，未发布到 Wiki。此错误不表示主仓库推送失败。

GitHub 官方说明：公开仓库可在 Free 套餐使用 Wiki；私有仓库 Wiki 需要 Pro、Team 或 Enterprise。当前 API 未提供账号套餐名称，无法仅凭返回状态确认是套餐限制还是其他设置限制。[GitHub Wiki 可用范围](https://docs.github.com/en/communities/documenting-your-project-with-wikis/about-wikis)

## Wiki 可用后如何同步

1. 在仓库 Settings → General → Features 启用 Wiki；若 GitHub 提示升级，需先满足私有仓库的功能条件。
2. 在仓库 Wiki 页面创建首个 `Home` 页面。GitHub 要求先创建页面，才能克隆 Wiki Git 仓库。[创建与编辑 Wiki](https://docs.github.com/en/communities/documenting-your-project-with-wikis/adding-or-editing-wiki-pages)
3. 克隆 `https://github.com/mianxiu/plasticityassettool.wiki.git` 到单独目录。
4. 将 `docs/wiki/` 中的页面和 `_Sidebar.md` 复制到 Wiki 仓库，保留其他已有页面。
5. 将文档内部的本地页面链接改为无 `.md` 后缀的 Wiki 页面名；主仓库源文件保留 `.md` 相对链接。
6. 在 Wiki 仓库提交并推送，检查首页、侧栏及页面链接。

启用前可直接阅读主仓库中的文档，内容与准备发布到 Wiki 的版本一致。此流程不需要改变仓库可见性，也不上传模型库、运行缓存或安装备份。
