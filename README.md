# Pytest-Veristand —— NI HIL 台架 pytest 测试框架

VeriStand 2020 台架的 pytest 原生测试框架。TestStand 存量用例迁移目标端。

## 机器分工（2026-11 实测确认）

- **开发机（D:，无 VeriStand；有 LabVIEW 2020~2025、Python 3.9.13/3.12）**：
  写代码、跑 `-m "not hil"`（锁单元测试、.seq 解析等纯 Python 部分）。
- **台架机（F:，VeriStand 2020 + Gateway + 已部署系统）**：跑 `-m hil`。
  已验证解释器：`F:\TongYuTestScript\python.exe`（自建 Python 3.9.13 x64）。

### 开发机（本机，已完成）

```bat
cd /d "D:\冷俊\Claude Code\Pytest-Veristand"
py -3.9 -m venv .venv                            :: ✓ 已建（3.9.13，与台架对齐）
.venv\Scripts\pip install -r requirements.txt    :: ✓ 已装（niveristand 4.0.0 公共源可装）
.venv\Scripts\pytest -m "not hil"                :: ✓ 3 passed
```

### 台架机

```bat
:: 0. 先确认你的 Python 支持 venv（一次性检查；嵌入式发行版没有 venv 模块）
F:\TongYuTestScript\python.exe -c "import venv; print('ok')"
::    若报错：去 python.org 装 3.9.13 x64 到独立目录，用新解释器替代下面的路径

:: 1. 把本仓库拷贝/克隆到 TongYuTestScript 之外的目录
cd /d F:\hil-pytest
git clone <仓库地址> .

:: 2. 用已验证的 3.9.13 建 venv、装依赖
F:\TongYuTestScript\python.exe -m venv .venv
.venv\Scripts\pip install -r requirements.txt

:: 3. 改 config/bench.yaml 两处：system_definition 真实路径 + reset_channels 真实别名
::    （tests/test_smoke_hil.py 里的 DesiredRPM 同步改）

:: 4. 验收
.venv\Scripts\pytest -m "not hil"
.venv\Scripts\pytest -m hil        :: 前提：先确认往复位通道写值物理安全（见 README 安全项）
```

远程附加（开发机直连台架 Gateway）：开发机当前未装 VeriStand，**暂不可用**——
需先装 VeriStand 2020（与台架同版本）并验证 bench.yaml 的 gateway 远程配置。

## 分层

- `conftest.py` —— session 级：配置 → 台架锁 → 连接/部署；function 级：安全状态复位
- `helpers/bench_lock.py` —— 台架互斥文件锁（原子创建 + 陈锁自动清理）
- `helpers/channel.py` —— 通道读写 + 稳态等待 wait_near
- `config/bench.yaml` —— 唯一的环境配置入口（可被 HIL_BENCH_CONFIG 环境变量覆盖）
- `tests/` —— 框架级用例（锁、smoke），`-m hil` 需台架；其余任何机器可跑
- `projects/<项目>/<模块>/` —— 两层结构：项目 = 一个车型/一套 VeriStand 工程（`p2546`，含
  `project.yaml` 的 veristand 覆盖段 + `common/` 共享通道/工况/判定）；模块 = 一个 `.seq`
  （`left_heating`：module.yaml + stimulus + tests + samples）。目录名规范成 Python 包名
  （`C206-10` → `c206_10`），`project.yaml` 的 veristand 段会覆盖 `config/bench.yaml`

## 台架占用规则（多人 + CI 共存的前提）

- 任何 pytest 会话（含 CI）启动即拿 `C:/HIL/bench.lock`，结束释放；拿不到按 `lock.on_busy` 处理。
- 手动双终端验收：终端 A 跑 `pytest -m hil`，期间终端 B 再跑一次 → B 应报"台架正被占用"。
- 白天人工一律 `mode: attach`（附加到已部署系统）；`mode: deploy`（完整部署）仅 CI 夜间窗口使用。

## 待办（P1 收尾清单）

- [x] niveristand 4.0.0 来源确认：公共 pip 源可直接安装（开发机已实证）
- [ ] 开发机装 VeriStand 2020（与台架同版本）+ 验证远程 Gateway attach
- [ ] .nivssdf 系统定义是否纳入版本管理（建议 git-lfs 或固定路径+变更记录）
- [x] hil 安全确认：欠压/继电器/IGN/FIU 均可写（2026-11-06 已通过）
