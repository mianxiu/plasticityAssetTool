# 从源码运行与界面更新

开发需要 **Windows、Python 3.10+ 和 Node.js/npm**。发布包用户无需执行这些命令。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\start.ps1
```

`start.ps1` 构建前端并启动后台；后台已经运行时复用现有实例。调试代码修改后，通过托盘退出旧后台再启动。

| 目录 | 内容 |
| --- | --- |
| `backend/` | 组件数据库、模型通信、预览、托盘与服务 |
| `plasticity-asset-tool-app/` | Solid Web UI |
| `plasticity-javascript-payloads/` | 内嵌面板与 Plasticity 原生工作脚本 |
| `installer/` | 插件安装、更新与恢复 |
| `packaging/` | Windows 发布包构建 |
| `tests/` | 自动测试与发布验证 |
| `docs/` | 安装、文件格式与性能说明 |

运行 Python 测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

前端构建、发布包与性能资料分别见 [应用目录](../../plasticity-asset-tool-app/)、[发布构建脚本](../../packaging/build_release.py) 和 [Tab 性能说明](../tab-performance.md)。生成程序、本地模型库、运行缓存和安装备份不提交到仓库。

## UI 自动更新

源码运行时，修改前端后在 `plasticity-asset-tool-app/` 执行 `npm run build`。已加载此功能的后台页面和 Tab 内嵌面板约每 3 秒检查新构建，校验 HTML、脚本与样式完整后，自动重载组件库页面；不会刷新 Plasticity 主界面，也不会重复投递模型操作。

保存、置入、编辑、右键旋转预览、批量导出和后台安装期间会延迟更新。隐藏的 Tab 面板等下次展开并空闲时更新；分组、搜索、分类与排序会恢复。断连或操作结果不明时先保留旧页面，不以刷新清除错误。

首次安装本功能，需要先让已有组件库页面加载新版本一次：后台页面可重新加载；旧的常驻 Tab iframe 可在自行保存文档后正常重启 Plasticity。之后仅更新前端构建无需重启宿主或后台。入口补丁、原生接口和 Python 后台代码的变更不属于此 UI 更新功能；打包版仍须先替换实际使用的前端文件。

构建时保留旧的带哈希资源，让尚未结束编辑的旧页面仍能加载所需模块；需要清理旧资源时，先退出使用这些页面的后台，再清理 `dist/` 并重新构建。

开发服务器的 `npm run dev` 使用 Vite 自带 HMR，生产构建使用上述安全更新流程。
