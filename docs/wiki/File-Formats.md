# 文件格式说明

以下描述对应当前源码实现。旧版本发布包不一定包含最新功能。

## 格式速查

| 文件或格式 | 用途 | 应如何使用 |
| --- | --- | --- |
| `.patasset` | 单个组件交换包，含模型和编辑信息 | 组件库“导入组件包”导入；“编辑 → 导出组件包”导出 |
| `PlasticityAssetTool-components.zip` | 批量导出的多个 `.patasset` | 先解压，再逐个导入；目前不能直接导入外层 ZIP |
| `library/library.sqlite3` | 所有组件、库、分组、归档及缓存的实际数据库 | 退出后台后备份整个 `library/`；不是组件包导入文件 |
| `.plasticity` | Plasticity 原生建模文档 | 在 Plasticity 打开，选择对象后保存组件；插件不直接导入整个文档 |
| `model.bin` | `.patasset` 内部的原始模型字节 | 由插件读取；不要单独打开或改后缀作为 CAD 文件 |
| `manifest.json` | `.patasset` 内部的组件元数据 | 记录名称、分类、默认布尔模式、连续布尔顺序和校验值 |
| `preview.jpg` | `.patasset` 内可选的手动预览图片 | JPEG 展示图，不含可编辑模型 |
| 自动几何网格和缩略图 | 数据库中的可重建预览缓存 | 由连接的 Plasticity 内核生成；不包含在导出的组件包内 |
| `PlasticityAssetTool.exe` | Windows 启动入口 | 与完整发布目录一起使用，不能只复制 EXE |
| `PluginInstaller.exe` | 发布包自带的插件安装器 | 从后台控制中心“插件安装”启动，确认目标及 Windows 权限 |
| `PlasticityAssetTool-windows-x64.zip` | 程序发布包，含启动器、运行时、插件和界面 | 解压运行，不包含个人组件数据库 |
| `.zip.sha256` | 程序发布 ZIP 的完整性校验值 | 比较文件 SHA-256；不是数字签名或模型文件 |
| `config.json`、运行状态 `.json` | 后台配置、面板设置或实例信息 | 不通过组件包入口导入 |
| `.ps1`、`.py`、`.js`、`.cjs`、`.ico` | 启动脚本、代码和图标 | 程序资源，不是组件模型 |

## `.patasset` 的内容

`.patasset` 是采用自定义后缀的 ZIP 容器。可以用 ZIP 工具查看，但正常交换时保留 `.patasset` 后缀。

```text
example.patasset
├── manifest.json     必需：UTF-8 JSON 元数据
├── model.bin         必需：原始 Plasticity 对象数据
└── preview.jpg       可选：手动上传的 JPEG 图片
```

一个组件可以包含多个实体、多个曲线、实体与曲线混合选择，或带连续布尔规则的实体组，不一定只有一个物体。

### 保留哪些信息

`manifest.json` 的格式标识是 `plasticity-asset-tool`，格式版本为 `1`。记录组件名称、分类、标签、备注、来源版本、模型 SHA-256、类型 `kind`、默认置入模式 `insert_mode` 及可选连续布尔配方 `recipe`，也包含原 ID、时间、库和分组 ID 等信息。

导入会创建**新 ID 和新时间记录**，并放入当前选中的库与分组。分类、标签、备注、类型、默认置入模式、连续布尔顺序及来源版本保留；原库/分组树不会重建，归档组件导入后成为普通未归档组件。因此组件包不能代替数据库完整备份。

`has_geometry`、`has_geometry_preview` 是导出时的状态标记，**不代表包里附带自动预览缓存**。手动预览图片可随包导出；自动正交缩略图与三维网格导入后需要重新生成。

### 原始模型是什么

`model.bin` 保存 Plasticity 原生对象序列化数据，与其专用剪贴板格式 `application/vnd.plasticity.items` 使用的模型编码一致。数据含对象选择信息、几何块和对象元数据；其中几何使用 Parasolid transmit 数据。

它不是独立 STEP、STL、OBJ 或 Parasolid `.x_t` / `.x_b` 文件。改后缀不会转换格式，也不能把它当完整 `.plasticity` 文档打开。默认保存和置入经插件内存通道传输，不依赖系统剪贴板；“仅复制到剪贴板”等明确操作仍使用剪贴板。

### 类型与布尔规则

| 字段 | 值 | 含义 |
| --- | --- | --- |
| `kind` | `solid` / `curve` / `mixed` / `unknown` | 实体 / 曲线 / 混合 / 未标注 |
| `insert_mode` | `new-body` | 独立对象 |
| `insert_mode` | `union` | 布尔合并 |
| `insert_mode` | `difference` | 布尔减去 |
| `insert_mode` | `intersection` | 布尔相交 |
| `recipe` | `null` 或顺序配方 | 连续布尔组的子部件名称、索引和运算模式 |

Curve 和混合组件仅独立对象置入，不使用布尔模式。连续布尔在点击“保存组件”时识别单个选中原生组；按直接子实体从上到下保存顺序。名称首个非空白字符 `+` 为合并、`-` 为减去、`&` 为相交、`^` 为独立对象，无前缀也为独立对象。普通多选不解析这些前缀。含曲线、子组或组外其他选择时不能保存为连续布尔组。

界面的“连续布尔”状态由配方计算，不是第五种 `insert_mode`。例如配方内容如下，仅示意规则，不能脱离有效 `model.bin` 构成可导入组件包：

```json
{
  "version": 1,
  "name": "外壳组件",
  "parts": [
    {"index": 0, "name": "+ 外壳", "mode": "union"},
    {"index": 1, "name": "- 内孔", "mode": "difference"}
  ]
}
```

### 当前格式限制

- 单包原始模型最多 64 MiB；手动 JPEG 最多 5 MiB；清单最多 64 KiB。
- 只接受上述必需文件和可选图片；多余文件、重复条目、未知格式版本及模型校验不一致会拒绝导入。
- 导入的包结构与 SHA-256 校验不代表已验证所有几何。置入和生成预览还会校验原生模型编码，并受 Plasticity 内核能力限制。
- 默认布尔需要置入前选择有效目标实体；当前原生工具未结束时需要先确认或退出。

## 批量导出 ZIP

批量包是外层 ZIP，内部每个文件都是完整 `.patasset`，文件名使用“组件名 + 完整组件 ID”，避免同名覆盖。单次支持 1–10000 个组件。

```text
PlasticityAssetTool-components.zip
├── 外壳--<组件ID>.patasset
└── 内孔--<组件ID>.patasset
```

外层 ZIP 不额外保存分类目录树或完整数据库。分类等信息在各组件清单中。当前需要解压后逐个导入，不能直接导入外层 ZIP，也没有一次选择多个单包的导入入口。

## 数据库和预览缓存

源码目录启动时，默认数据库是 `G:\Github\plasticityAssetTool\library\library.sqlite3`；发布版在对应安装目录的 `library/` 中保存。

| 数据表 | 保存内容 |
| --- | --- |
| `assets` | 原始模型 BLOB、元数据、可选手动图片、归档状态和连续布尔配方 |
| `libraries` / `folders` | 库名称、分组名称及父子关系 |
| `geometry_cache` | 以模型 SHA-256 为键的 zlib 压缩 JSON 网格与自动 JPEG 缩略图 |
| `asset_metadata` | 用于快速浏览的可重建轻量元数据索引 |

自动预览使用正交投影，从模型自身的面和曲线生成，不是视口截图。它们是显示缓存，不能替代原始几何。相同模型可以共用缓存；缓存生成后，关闭 Plasticity 仍能查看。没有缓存时首次生成需运行已加载对应插件的 Plasticity。

“归档”不会删除原始模型。迁移所有库、分组、归档和缓存时，退出后台后复制整个 `library/`，不要只导出当前库组件。

## 配置、安装备份与程序包

`.runtime/panel-settings.json` 保存卡片尺寸、面板位置、侧栏展开方式等本机设置；`.runtime/backend-instance.json` 是后台进程状态；`.log` 是诊断日志。界面语言偏好保存在浏览器本机存储，不在组件包中。

安装器生成的原入口 `.js` 备份和对应 `.manifest.json` 用于恢复 Plasticity 插件入口，**不是组件包的 `manifest.json`**。保留这些备份有助于回滚安装；不要通过“导入组件包”导入它们。

源码提交到主仓库，生成的 Windows 程序 ZIP/EXE 应放在 GitHub Releases。个人 `library/`、运行状态、日志及安装备份不上传源码仓库或 Release。

插件当前不直接提供整个 `.plasticity` 文档或 STEP/IGES/STL/OBJ 等格式的导入导出入口。需要 CAD 格式转换时，在 Plasticity 本身使用该版本支持的导入导出命令。
