# left_heating —— P2546 左后大屏加热（模块）

项目级共享（通道常量、台架工况基类、EQ 判定）在上一级 `projects/p2546/common/`；
VeriStand 系统定义在 `projects/p2546/project.yaml`，台架级（Gateway、锁、Allure）在仓库根 `config/bench.yaml`。

## 目录

| 文件 | 作用 |
|---|---|
| `module.yaml` | 模块元信息（seq/历史报告/dump 路径） |
| `stimulus.py` | 本模块激励（继承 `common/bench.py` 的 BenchStimulus：加热档位/NTC/输出故障/采集） |
| `conftest.py` | 模块级 `bench` fixture（原文初始化/结束；新模块可照抄） |
| `tests/` | 用例，按类别分文件（见下表） |
| `samples/` | 存量 `.seq` + TestStand 历史报告（只读参考，勿改） |

## 用例覆盖（33 条：30 passed / 3 xfailed）

| 文件 | 条数 | 覆盖的存量序列 |
|---|---|---|
| `tests/test_heating.py` | 7 | 触发条件 3 档 + OFF、欠压 前提/退出、故障恢复-NTC短地 |
| `tests/test_conditions.py` | 4 | 过压 前提/退出、整车碰撞 前提/退出 |
| `tests/test_engine_state.py` | 6 | 发动机状态 前提 3（NoRunning/Crank/Fault）、退出 2、暂停 1（Crank） |
| `tests/test_ignition.py` | 7 | 点火开关 前提 4（OFF/ACC/CRANK+IG/Error）、退出 3（OFF/ACC/Error） |
| `tests/test_ntc.py` | 5 | NTC 短电源/开路 前提+退出（CH7）、故障恢复-NTC开路（CH9） |
| `tests/test_output_fault.py` | 4 | 加热输出短地 前提/退出（xfail）、故障恢复 欠压、故障恢复 过压（xfail） |

**xfail(strict) 三条 = 已记录的缺陷/待确认项**：

1. `前提条件测试-加热输出短地`、`退出条件测试-加热输出短地` —— 复现存量历史 Failed（实测 hard=1/CAN=4，期望 0/1）
2. `故障恢复测试-过压故障` —— 实测过压后不自恢复（20s 仍 hard=0/CAN=1），按压加热开关才恢复；原文不按开关

**尚未翻译**（原文 MainSequence 整条 Skip，需用户确认是否启用）：
前提/退出条件-加热输出开路、故障恢复-输出短地/开路、加热输出稳定性-40min。

## 运行

```bat
cd /d "F:\Cloude code\Pytest-Veristand"

:: 本项目全部用例（约 6 分钟）
F:\TongYuTestScript\python.exe -m pytest projects\p2546\left_heating\tests

:: 单文件/单条
F:\TongYuTestScript\python.exe -m pytest projects\p2546\left_heating\tests\test_ignition.py
F:\TongYuTestScript\python.exe -m pytest "projects/p2546/left_heating/tests/test_heating.py::test_trigger_off"
```

## 重新生成 dump（改了/换了 .seq 之后）

```bat
F:\TongYuTestScript\python.exe tools\seq_dump.py ^
  "projects\p2546\left_heating\samples\P2546_左后大屏加热.seq" ^
  -o "reports\P2546_左后大屏加热_dump.json"
```

## 本项目已确认的台架机制（改代码前必读）

| 事项 | 结论 |
|---|---|
| 判定语义 | 原文 Numeric Limit 为 `EQ`：实测 == `Limits.Low`，High(=11) 不参与 |
| 档位编码 | `0=无请求（保持状态）/ 1=OFF / 2=一档 / 3=二档 / 4=三档` |
| 档位请求时序 | 库序列含 2s 内部等待 → 用 `Stimulus.request_heat()` |
| NTC 通道 | 前提/退出系列用 CH7；故障恢复系列用 CH9 |
| 输出故障通道 | CH1（开路=2/短地=1），短地时另写 CH10=2 |
| CH10 复位 | 原文永不复位 CH10，会泄漏给后续用例 → `reset_channels` 已补 |
