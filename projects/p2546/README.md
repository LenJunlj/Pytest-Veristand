# p2546 —— P2546 项目（HIL 测试迁移）

一个项目 = 一个车型/一套 VeriStand 工程（`E:\P2546\Veristand项目\p2546.nivsproj`，模型 TongYu_IO），
下含多个 `.seq` 模块。本目录的 `project.yaml` 携带本项目自己的 `veristand.system_definition`，
会覆盖台架级 `config/bench.yaml` 的同名配置（多项目互不干扰）。

## 结构

| 位置 | 作用 |
|---|---|
| `project.yaml` | 项目级配置：显示名、epic、veristand 覆盖段、模块清单 |
| `common/channels.py` | 通道常量与值域（档位编码、FIU 注入值——项目级事实，跨模块共用） |
| `common/bench.py` | `BenchStimulus` 台架工况基类（初始化/结束、电源/点火/电源模式/发动机/碰撞） |
| `common/checks.py` | 判定断言（原文 EQ 语义：实测 == Limits.Low） |
| `<模块>/` | 一个 `.seq` 一个模块：`module.yaml` + `stimulus.py` + `tests/` + `samples/` |

## 模块清单

| 模块 | 内容 | 状态 |
|---|---|---|
| `left_heating/` | 左后大屏加热（33 条用例：30 passed / 3 xfailed） | ✅ 已迁移 |
| `right_heating/` | 右后大屏加热 | 待铺开（.seq 在 E:/P2546/用例库/第一轮/测试用例/） |
| `tbox_left/`、`tbox_right/` | TBOX 远程加热功能 | 待铺开 |
| `dtc/` | DTC 测试 | 待铺开 |

## 新建模块的步骤

1. `mkdir <模块>/{tests,samples}`，加 `__init__.py`（模块目录与 tests 目录都要）
2. 拷贝存量 `.seq` 与历史报告进 `samples/`
3. `python tools/seq_dump.py "projects/p2546/<模块>/samples/xxx.seq" -o reports/xxx_dump.json`
4. 写 `stimulus.py`：`class Stimulus(BenchStimulus)`，只加本模块特有激励
5. 写 `module.yaml`（seq/报告/dump 路径）与 `tests/`（bench fixture 参照 `left_heating/conftest.py`）

## 新建项目（如 C206-10）

复制本目录为 `projects/c206_10/`（目录名规范成 Python 包名），改 `project.yaml` 的
`system_definition` 指向新项目的 `.nivssdf`，通道/工况按新模型重建 `common/`。
台架级（Gateway、锁、Allure）仍在 `config/bench.yaml`，不用动。
