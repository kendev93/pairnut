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
- SQLite 本地存储
- 按品种管理核桃与配对规则
- 基于边 / 肚 / 高偏差、克重接近度、瑕疵扣分的候选配对

## 启动

在项目根目录执行：

```bash
python3 -m pip install -r requirements.txt
python3 main.py
```

## 打包

GitHub Actions 已配置桌面端打包流程：

- 手动运行 `Build desktop packages`
- 推送 `v*` 标签时自动运行
- Windows 产出 `PairNut.exe`
- macOS 产出 `PairNut-macOS-*.dmg`
- 推送 `v*` 标签时自动创建 GitHub Release，并挂载 exe / dmg

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
├── data/
│   └── pairnut.db           # 首次运行后自动创建
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
