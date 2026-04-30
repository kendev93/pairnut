# PairNut

[![CI](https://github.com/kendev93/pairnut/actions/workflows/ci.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/ci.yml)
[![Build desktop packages](https://github.com/kendev93/pairnut/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/build-desktop.yml)
[![CodeQL](https://github.com/kendev93/pairnut/actions/workflows/codeql.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/codeql.yml)
[![License](https://img.shields.io/github/license/kendev93/pairnut)](LICENSE)

![PairNut Cover](assets/cover.png)

核对（PairNut）是一款面向文玩核桃商家的本地智能配对工具。

PairNut 的目标是提供通用的本地配对解决方案：用户可以只录入边 / 肚 / 高和克重，也可以导入六面图，后续还可以导入第三方扫描或建模软件生成的 3D 模型。软件不绑定具体扫描仪或采集方式，而是按可用证据动态生成候选配对。

当前版本聚焦本地桌面使用场景：

- PySide6 桌面界面
- Python 业务逻辑
- SQLite 本地存储，开发态使用项目 `data/`，打包后按系统使用稳定的数据目录
- 按品种管理核桃与配对规则
- 基于边 / 肚 / 高偏差、克重接近度、瑕疵扣分的候选配对
- 按 `核桃编号-序号` 批量导入六面图，提取 OpenCV 特征并在候选配对中显示图片相似度
- 启动后自动检查 Gitee Release 新版本，并引导用户下载更新

## 启动

在项目根目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

## 数据目录

开发运行时，默认数据仓库在项目目录内：

```text
data/
```

打包后的应用不把业务数据放在软件安装目录中，默认数据仓库按系统区分：

```text
macOS:   ~/Library/Application Support/PairNut/
Windows: C:\ProgramData\PairNut\
Linux:   $XDG_DATA_HOME/PairNut/ 或 ~/.local/share/PairNut/
```

其中 `pairnut.db` 保存核桃、品种、配对记录和图片特征值；导入图片会放在该目录下的 `images/`。当前图片匹配使用 OpenCV 特征，不需要下载模型。后续如加入可选 AI 或 3D 模型，模型文件会放在同一数据目录下的 `models/`，由需要该功能的用户自行下载或在模型管理中下载。升级或重装软件时，不要删除这个数据目录。应用菜单中的“文件 -> 打开数据目录”可以直接打开该文件夹，方便用户备份或管理图片；“文件 -> 模型管理”用于查看、下载、删除和切换特征模型，“文件 -> 打开模型目录”用于管理模型文件。

开发和测试可通过 `PAIRNUT_DATA_DIR` 指向临时目录。开发态的项目内 `data/` 不会自动迁移到打包后的用户数据目录。

## 图片导入

先在“核桃管理”里创建好核桃编号，再点击“批量导入图片”选择图片文件。文件名需要使用 `核桃编号-序号.扩展名`，序号范围为 `1` 到 `6`。

示例：

```text
NJS-01-1.JPG
NJS-01-2.JPG
NJS-01-3.JPG
```

也支持下划线或空格分隔，例如 `NJS-01_1.JPG`。导入时只匹配当前选中品种下已有的核桃编号，无法匹配的图片会在导入结果里提示。

导入成功后，应用会基于 OpenCV 提取颜色、纹理和形状特征，特征值保存到 SQLite。候选配对会在双方都有对应面特征时显示图片相似度；图片缺失时不影响尺寸和重量配对。

当前 OpenCV 图片匹配无需额外下载模型；只有未来启用可选 AI 模型或 3D 模型能力时，才需要把模型文件放入“文件 -> 打开模型目录”指向的位置。

## 模型管理

“文件 -> 模型管理”会显示当前可用的特征模型。当前内置的是 `OpenCV 基础特征`，无需下载模型文件；可选 AI 模型会以模型清单形式出现，发布下载地址后用户可直接下载到数据目录下的 `models/`，也可以手动把模型文件放入该目录再启用。删除可选模型只会删除本地模型文件，不会删除核桃图片或数据库。切换模型后，需要重新提取已有图片特征，才能让候选配对使用新模型的特征值。

## 打包

GitHub Actions 已配置桌面端打包流程：

- 手动运行 `Build desktop packages`
- 推送 `v*` 标签时自动运行
- Windows 产出 `PairNut.exe`
- macOS 产出 `PairNut-macOS-*.dmg`
- 推送 `v*` 标签时自动创建 GitHub Release，并挂载 exe / dmg
- 客户端通过 Gitee 最新 Release 判断是否有新版本；当前版本只提示下载，不后台替换程序

本地构建图标资源：

```bash
python3 -m pip install -r requirements-build.txt
python3 scripts/build_icons.py
```

## 自动化

- `CI`：push / PR 自动运行编译检查和测试
- `Build desktop packages`：手动或 tag 触发桌面端打包
- `CodeQL`：自动做 Python 代码安全扫描
- `Dependency audit`：每周扫描 Python 依赖漏洞
- `Dependabot`：每周检查 Python 依赖和 GitHub Actions 更新

## 当前目录

```text
pairnut/
├── main.py
├── requirements.txt
├── requirements-build.txt
├── assets/
│   ├── cover.png
│   └── icon.png              # 应用图标建议放这里
├── pairnut/
│   ├── app.py
│   ├── database/
│   ├── domain/
│   ├── services/
│   └── ui/
├── scripts/
│   └── build_icons.py
└── tests/
```

## 首版范围

- 品种先创建，再录入核桃
- 同品种内推荐配对
- 每个品种一个统一偏差值，默认 `1mm`
- 每颗核桃返回 `3` 个候选参考
- 支持锁定、解除锁定、拉黑

## 暂不包含

- 可选 AI 模型自动下载
- Excel / CSV 导入导出
- 云同步与联网配对
