# PairNut Agent 开发指南

本文件用于约束 AI 编码代理和维护者在本仓库中的工作方式。内容以项目实际需要为准，避免泛泛而谈。

## 沟通规则

- 默认使用中文与项目 owner 沟通。
- 说明问题时要直接、具体，优先给出可执行结论。
- 不要擅自扩大任务范围。用户要求改什么，就只处理对应范围。
- 未经用户明确允许，不要修改与当前任务无关的文件、格式、依赖、配置或文档。
- 如果发现顺手可修的问题，先说明风险和建议，等待用户确认后再改。
- 如果工作区已有未提交改动，默认认为是用户的改动；不要回滚、覆盖或重排这些改动。

## 实现原则

- 采用最小规模实现：用最少的代码解决当前问题。
- 优先沿用现有架构、命名、文件组织和代码风格。
- 不为单个小问题引入新的抽象、框架或复杂流程。
- Bug fix PR 应聚焦修复本身，避免夹带重构、格式化或无关优化。
- 修改公共逻辑、数据库结构、匹配规则或 UI 行为时，必须补充或更新对应测试。
- 对用户数据保持保守：正常应用代码不得删除、重写或迁移失败后破坏已有数据库。

## 项目概览

PairNut 是一款面向文玩核桃商家的本地桌面配对工具。

- UI：PySide6 桌面应用。
- 存储：本地 SQLite。
- 入口：`main.py`。
- 核心包：`pairnut/`。
- 测试：`tests/`，测试代码基于 `unittest`，通常用 `pytest` 运行。

开发环境默认数据库位置是 `data/pairnut.db`。打包后数据库跟随平台数据目录：macOS 为 `~/Library/Application Support/PairNut/pairnut.db`，Windows 为 `C:\ProgramData\PairNut\pairnut.db`，Linux 为 `$XDG_DATA_HOME/PairNut/pairnut.db` 或 `~/.local/share/PairNut/pairnut.db`。测试必须通过 `PAIRNUT_DATA_DIR` 指向临时目录，避免碰真实用户数据。

## 常用命令

本环境可能没有 `python` 命令，统一使用 `python3`。

```bash
python3 -m pip install -r requirements.txt
python3 main.py
pytest -q
python3 -m compileall main.py pairnut tests scripts
```

无桌面环境或 CI 中运行 UI 冒烟测试：

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

只有修改 `assets/` 图标资源时才需要构建图标：

```bash
python3 -m pip install -r requirements-build.txt
python3 scripts/build_icons.py
```

## 目录职责

- `pairnut/database/connection.py`：数据目录和 SQLite 连接。
- `pairnut/database/schema.py`：建表、索引和轻量迁移。
- `pairnut/database/repositories.py`：SQL 读写、配对归一化。
- `pairnut/services/`：配对、评分、编号等业务逻辑。
- `pairnut/ui/views.py`：PySide6 界面和事件处理。
- `pairnut/domain/models.py`：共享领域数据结构。

尽量不要把业务规则写进 `pairnut/ui/views.py`。匹配和评分逻辑放在 `pairnut/services/`，持久化规则放在 `pairnut/database/`。

## 数据库规则

- 存储或比较核桃配对前，必须使用 `repositories.normalize_pair()`。
- `locked_pairs` 表要求 `walnut_id_1 < walnut_id_2`。
- 活跃锁定表示 `is_active = 1`；解锁后的历史记录保留在表中，`is_active = 0`。
- `locked_pairs` 的唯一约束只能限制活跃记录：

```sql
CREATE UNIQUE INDEX idx_locked_pairs_active_pair
ON locked_pairs (walnut_id_1, walnut_id_2)
WHERE is_active = 1
```

不要恢复 `(walnut_id_1, walnut_id_2, is_active)` 唯一索引。它会阻止同一对核桃产生多条已解锁历史记录，破坏重复“锁定 -> 解锁 -> 再锁定 -> 再解锁”的流程。

修改 schema 或迁移逻辑时，必须补充使用临时数据库的测试。

## 测试要求

合并代码前至少运行：

```bash
pytest -q
python3 -m compileall main.py pairnut tests scripts
```

数据库变更优先补测试到 `tests/test_schema.py` 或 `tests/test_matching.py`。

UI 变更要兼容 `QT_QPA_PLATFORM=offscreen`。除非测试明确使用 mock，否则不要写依赖真实可见桌面的断言。

## PR Review 清单

审查 PR 时：

- 先看 `git diff main...HEAD`。
- 确认改动范围是否和 PR 目标一致。
- 拒绝无关格式化、依赖升级或大范围重构，除非用户明确要求。
- 检查数据库迁移、匹配规则、UI 行为是否有测试覆盖。
- 运行“测试要求”里的命令。
- 注意测试是否可能误碰真实本地数据库。
- 依赖变更要同时检查 `requirements.txt`、CI 和实际 import 位置。

GitHub PR 本地检出方式：

```bash
git fetch origin pull/<PR_NUMBER>/head:review/pr-<PR_NUMBER>
git checkout review/pr-<PR_NUMBER>
```

## 代码风格

- 函数保持直接、短小、易读。
- SQLite 查询必须使用参数化查询。
- 用户可见中文文案要和现有 UI 风格保持一致。
- 不要在修 bug 时顺手做大规模重构。
- 不要在没有必要时新增顶层文件、配置文件或依赖。

## 已知注意事项

- 本地可能没有 `python`，使用 `python3`。
- SQLite partial index 是活跃配对唯一性的关键。
- 测试必须用 `PAIRNUT_DATA_DIR` 隔离数据库。
- PySide6 冒烟测试在 CI/headless 环境应设置 `QT_QPA_PLATFORM=offscreen`。
