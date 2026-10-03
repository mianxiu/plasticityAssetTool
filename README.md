# plasticityAssetTool

Windows 上的 Plasticity 模型组件库。保存选中实体的原生剪贴板数据，点击组件后调用 **Ctrl+Shift+V**，在 Plasticity 视口里定位、调整并确认置入。

## 启动

在项目目录的 PowerShell 中运行：

```powershell
.\start.ps1
```

脚本构建 Solid 前端并启动本地服务，浏览器打开 `http://127.0.0.1:15150`。需要 Node.js/npm 和 Python 3.10+；脚本会尝试项目虚拟环境、Codex 自带 Python 和已安装的 Python。项目内的旧虚拟环境即使原解释器丢失，也可以复用其纯 Python Tornado 包。

使用独立 Python 环境时：

```powershell
python -m pip install -r requirements.txt
cd plasticity-asset-tool-app
npm install
npm run build
cd ..
python main.py
```

已有构建可运行 `.\start.ps1 -NoBuild`；`-Headless` 只启动服务。服务只监听本机。应从普通桌面终端启动，以便读取本机 Plasticity 窗口；开发沙箱可能无法枚举桌面进程。

## 保存和置入组件

1. 打开源 `.plasticity` 模型，选中需要复用的实体或多个实体，退出当前工具，在视口中按 **Ctrl+C**。
2. 打开组件库，点击“保存组件”，填写名称、分类、标签和备注。可附加 JPEG 预览图。
3. 选择目标 Plasticity 窗口，点击组件卡片的“置入”。工具把保存的原始模型字节恢复到 Plasticity 自定义剪贴板格式，然后发送 **Ctrl+Shift+V**。
4. 在 Plasticity 视口点击定位。置入期间可按 **S** 缩放（例如输入 `2` 放大两倍）、**A** 调整角度、**D** 偏移；**F** 翻转，**X/Y/Z** 调整朝向。数值调整按 Enter 确认，再按 Enter 完成置入。原生工具会继续等待下次定位，可重复置入，**Esc** 退出。后续可用组件库的移动、旋转、缩放按钮调用原生工具。

“自动复制目标窗口当前选中的模型”会先发送 Ctrl+C，再等待新的剪贴板数据；未检测到更新则不保存旧数据。“仅复制到剪贴板”不控制视口，可以自行切换窗口并按 Ctrl+Shift+V。“原位置粘贴”单独调用 Ctrl+V。

桌面快捷键模式需要 Plasticity 的视口保持焦点，并结束正在进行的其他工具或文本编辑。修改过快捷键的用户可在 `config.json` 的 `keymap.desktop_shortcuts` 中配置。工具不会自动确认或取消你的建模操作。发送命令后界面提示“已发送”，不会把输入发送成功当成建模成功。

## 组件库和备份

- 资产库标签支持新建、切换和重命名；旧组件自动归入“默认库”。每个库独立显示组件、分类、分组和归档数量，仍统一保存在同一个 SQLite 数据库中。
- 库内支持嵌套分组，侧栏和路径导航可以进入子分组。保存或编辑组件时可选择所属库、分组，以及 Solid / Curve / 混合 / 未标注类型；跨库移动保留原始模型字节，导入组件包使用当前库和当前分组。
- 分组是组件库的组织结构，类型由用户标注。目前不会自动解析或恢复 Plasticity 原生组树、对象 ID、对象名称，也不提供自动布尔。分组内的子组件可以独立置入；分组本身不会自动合并为一个模型。
- 搜索覆盖当前库的所有分组；Ctrl+K 聚焦搜索，Enter 置入第一项结果，随后仍需在 Plasticity 视口定位并确认。

- 数据保存在 `library/library.sqlite3`，包含原始模型字节、元数据和可选 JPEG 预览；该目录不会进入 Git。关闭服务后复制整个 `library` 目录即可备份。
- 支持分类与搜索、编辑信息、归档和恢复。归档保留模型数据。编辑组件时可以替换或移除 JPEG 预览图；只编辑信息会保留原图。列表和预览请求只读取所需数据，避免每次刷新都加载全部模型字节。
- 单组件可以导出 `.patasset` 包再导入，导入会校验模型摘要。原生剪贴板格式是 Plasticity 内部格式，跨版本、跨电脑和 Windows 重启后的兼容性尚未实机验证。此包不是通用 CAD 交换格式。
- 目前 `.plasticity` 文件需先在 Plasticity 打开并复制所需实体；组件库不会把一个完整文档直接当作实体插入，也不会替换目标文档。

## 快捷唤起

Windows 服务运行期间，在 Plasticity 前台按 **Tab** 打开组件库并聚焦搜索；面板打开时再按 **Tab** 关闭并交回建模窗口，**Esc** 或右上角 × 也可收起。Tab 仅在 Plasticity 或它的组件库面板前台生效；其他应用、Shift+Tab 和 Ctrl+Tab 不受影响。面板中的单独 Tab 优先切换开关，可用 Shift+Tab 或鼠标选择表单字段。长按不会连续切换。使用 Tab 会覆盖 Plasticity 原有的同键功能，如需保留请更换唤起键。

当前配置使用真正的 iframe 内嵌模式，通过下面的 main 入口补丁安装到 Plasticity 建模窗口。`launcher.enabled: false` 避免旧的桌面 Tab 钩子抢占按键。本地服务仍需要运行，可使用 `.\start.ps1 -Headless -NoBuild`。如需原来的 Edge 无边框附属浮层，应先恢复 main 入口，再启用 `launcher.enabled`；该浮层模式不是 DOM 内嵌。

组件库触发置入、复制选中实体或建模快捷键时会收起并交回所选 Plasticity 窗口。服务确认目标窗口获得焦点后才发送按键，切换失败会恢复组件库并报错。仅收起标题和进程匹配的组件库 Edge 窗口，不收起其他浏览器页面。2026-10-03 已实测从前台独立窗口交还焦点并进入 Ctrl+Shift+V 原生定位工具，取消测试后原有三个实体保留。

`config.json` 的 `launcher.enabled` 关闭唤起功能，`launcher.shortcut` 更换为 `tab`、`f8`、`ctrl+alt+space` 等（修改后重启服务）；`launcher.frameless: false` 恢复独立有边框窗口。单键使用只针对 Plasticity 的键盘钩子，组合键使用 Windows 快捷键注册；注册失败会在页脚提示。服务退出时释放钩子/快捷键并恢复组件库原来的窗口样式。`-Headless` 不自动打开浏览器，但保留按键唤起功能。

## 真正的内嵌面板

`main_embed_install.py` 在 `resources/app/.webpack/main/index.js` 前添加 Electron 加载钩子，保留原始编译加载器字节和 `index.compiled.jsc`。建模页面完成加载后注入 iframe，默认隐藏，第一次 Tab 才加载组件库。不修改 renderer HTML，也不需要 CDP。每个窗口的 URL 自动带上它自己的 HWND，避免将组件发到其他建模窗口。

Tab 在 Electron 输入层处理，并兼容原生/模拟输入的 `code` 和 `key`，忽略组合键及长按重复；面板获得焦点后仍可再次 Tab 关闭。首次加载通过 `pat:ready` 握手，避免向尚未加载的子页面发送消息。置入前隐藏 iframe、聚焦 CAD 画布，收到焦点确认后发送 Ctrl+Shift+V；操作失败时重新显示面板和错误提示。Esc / × 也可收起。

安装前关闭 Plasticity，在有安装目录写权限的终端运行（替换版本路径）：

```powershell
python main_embed_install.py --target "C:/Program Files/Plasticity/app-26.1.3/resources/app/.webpack/main/index.js" --backup ".runtime/plasticity-formal-main-original.js"
```

使用内嵌模式时将 `launcher.enabled` 设为 `false`；`keymap.show_panel_event_key_code` 指定按键，如 `Tab` 或 `F8`，改键后需要先恢复入口，再重新安装补丁并重启 Plasticity。服务继续使用 `.\start.ps1 -Headless`。正式安装不要传 `--profile`，它只用于测试副本的 Electron 配置隔离。

恢复入口使用 `python main_embed_install.py --restore --backup ".runtime/plasticity-formal-main-original.js"`，需要安装目录写权限（通常需管理员终端或手动确认 Windows UAC）。备份和 manifest 记录原始、补丁 SHA-256；恢复会拒绝覆盖补丁之后的其他修改。Plasticity 更新后应检查新的版本入口并使用新的备份路径。旧 `embedded_install.py` 的 HTML 方案保留为实验脚本，当前不使用。

另一条路径是配置 `plasticity.cdp_endpoints` 为已有的本机 CDP 地址。检测到调试页面后会出现单独的 CDP 目标和“嵌入面板”按钮，同样使用 iframe，重复安装复用原面板；此路径不修改安装文件。

本机安装版本为 26.1.3。2026-10-03 已在真实 Plasticity 测试副本中验证 iframe 内嵌、两次无调试参数启动、Tab 重复开关、Esc 收起，以及原生组件置入、S 输入 2 放大两倍、确认新增实体和撤销。经用户批准已安装正式 main 补丁，正式窗口也完成两次无调试参数启动、插件加载、Tab 打开/关闭，以及置入、两倍缩放和撤销验证。测试受限沙箱中的 GPU 子进程加载失败，而完整桌面权限下正常启动成功。验证限于本机当前版本，跨版本、跨电脑和长期运行尚未验证。启动记录保存在 `.runtime/formal-embedded-startup-1.log`、`.runtime/formal-embedded-startup-2.log`，安装备份为 `.runtime/plasticity-formal-main-original.js` 及其 manifest。

## 开发和验证

2026-10-03 正式安装已实机验证：真正的 iframe 内嵌面板点击组件后进入 Ctrl+Shift+V，S 输入 2 放大两倍，确认后实体数量由 4 增至 5，Esc 退出连续置入，撤销恢复原场景。测试副本及正式版本验证 Tab 重复开关和正常重启。62 项 Python 测试通过，前端生产构建通过；安装器测试覆盖原始字节恢复、重复安装拒绝、其他修改保护，以及权限失败后利用已验证备份重试。切换逻辑测试覆盖连续 20 次开关、不同模型目标、隐藏后重开和无效目标；建模目标识别排除同进程的调试控制台。

```powershell
python -m unittest discover -s tests -v
cd plasticity-asset-tool-app
npm run build
npm run dev
```

开发前端运行于 3000 端口，WebSocket 连到 15150，HTTP API 由 Vite 转发。测试使用隔离目录和模拟桌面，不操作实际模型或系统剪贴板；覆盖存储与组件包往返、归档恢复、默认 Ctrl+Shift+V、普通粘贴、失效窗口、并发请求、CDP 响应匹配及 HTTP/WebSocket 协议。

## 历史实验记录

下方为早期剪贴板格式观察，未经当前版本验证；运行流程已由上述组件库入口替代。`program_info.py`、`test.py` 等旧实验脚本不再进入主程序调用链。

window

```sh
python -m venv ./
```

`https://unpkg.com/browse/htm@3.1.1/preact/`

剪贴版形状字节类型[3-4]:

HEAD:`79C4` [00-01] 每电脑不同
注册剪贴版生成的字节: [02-05]:
ITEM 数量:`Int32` [06-09] 无符号 0 到 4,294,967,295

PICK_UP_POINT 点坐标距离原点 = `Double` 是倍数\*自身在轴上的长度

- 8 字节 [] `X Axie` 倍数
- 8 字节[] `Y Axie`
- 8 字节[] `Z Axie`

# Commends

File:select_plasticity_file
