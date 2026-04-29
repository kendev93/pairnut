# PairNut

[![CI](https://github.com/kendev93/pairnut/actions/workflows/ci.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/ci.yml)
[![Build desktop packages](https://github.com/kendev93/pairnut/actions/workflows/build-desktop.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/build-desktop.yml)
[![CodeQL](https://github.com/kendev93/pairnut/actions/workflows/codeql.yml/badge.svg)](https://github.com/kendev93/pairnut/actions/workflows/codeql.yml)
[![License](https://img.shields.io/github/license/kendev93/pairnut)](LICENSE)

![PairNut Cover](assets/cover.png)

核对（PairNut）是一款面向文玩核桃商家的本地智能配对工具。

当前版本聚焦本地桌面使用场景：
- PySide6 桌面界面
- Python 业务逻辑
- SQLite 本地存储，按系统使用稳定的数据目录
- 按品种管理核桃与配对规则
- 基于边 / 肚 / 高偏差、克重接近度、瑕疵扣分的候选配对
- 启动后自动检查 Gitee Release 新版本，并引导用户下载更新

## 启动

在项目根目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

## 数据目录

PairNut 的业务数据不放在软件安装目录或源码目录中。默认数据仓库按系统区分：

```text
macOS:   ~/Library/Application Support/PairNut/
Windows: C:\ProgramData\PairNut\
Linux:   $XDG_DATA_HOME/PairNut/ 或 ~/.local/share/PairNut/
```

其中 `pairnut.db` 保存核桃、品种和配对记录；后续导入图片会放在该目录下的 `images/`。升级或重装软件时，不要删除这个数据目录。应用菜单中的“文件 -> 打开数据目录”可以直接打开该文件夹，方便用户备份或管理图片。

如果旧版本已经在 `~/Documents/PairNut/` 或项目内 `data/` 目录生成过数据，新版本首次启动会在新默认目录没有数据库时自动复制过去一次。开发和测试可通过 `PAIRNUT_DATA_DIR` 指向临时目录。

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

- 图片识别与六面图匹配
- Excel / CSV 导入导出
- 云同步与联网配对
