# Excel 用例 → 测试脚本 生成方案（供评审）

- **日期**：2026-11-07；**状态**：方案稿，评审拍板后才实施
- **背景**：后续项目不再有存量 `.seq`（老项目产物），用例将由人工写 Excel；VeriStand 工程自己搭。
  Excel 用例**不含** DI 口号、FIU 故障通道等物理信息——这正是本方案要解决的核心缺口。
- **前置积累**（已落地，本方案直接复用）：通道分层 D1~D5（bench_io/项目/模块三层）、
  双项目 sdf 实证、`tools/analyze_sdf.py`、`tools/gen_tests.py` 渲染内核、`tools/compare_draft.py`

---

## 1. 问题定义

| 信息来源 | 提供什么 | 缺什么 |
|---|---|---|
| Excel 用例（人写） | 步骤、动作、参数、期望值（**功能语言**："请求三档"、"加热输出应为 1"） | 通道地址、值编码、通道分工 |
| .seq（老项目） | 上述全部（变量全路径硬编码） | ——（但新项目不再有） |
| sdf | 通道全集与拓扑（**硬件语言**） | 功能语义（哪路是"加热输出"） |

缺的那一层 = **功能词 ↔ 通道 的绑定**。它是"模块事实"，一个模块只定义一次、全员复用。
所以答案不是"在 Excel 里标通道"，而是**一份独立的绑定配置文件**。

## 2. 方案总览：词汇表驱动生成

```
Excel 用例(纯功能语言)  +  bindings.yaml(词汇表:功能词→通道+值域)  +  bench_io/registry.csv(硬件存在性)
                         ↓ tools/gen_from_excel.py（复用 gen_tests 渲染内核）
                  draft_all.py（单文件/序号=Excel 行序/断言 EQ）+ gen_manifest.md
                         ↓ 人工复核（compare_draft 对账）→ 迁入 tests/
```

**关键设计：Excel 完全不含通道。** 测试员只写功能语言；通道只在 `bindings.yaml` 出现一次。
好处：①测试员不需要台架知识；②通道调整只改一个文件；③词汇表即"用例↔代码"对照表，天然满足你们的 Excel mapping 需求。

## 3. `bindings.yaml`（每模块一份，签核一次）

位置：`projects/<项目>/<模块>/bindings.yaml`（与 module.yaml 平级）。

| 字段 | 说明 |
|---|---|
| `signal` | **Excel 里出现的功能词**（动作词/期望词，必须完全一致） |
| `channel` | 通道标识：台架层相对标识（`RT_DO0`/`FIU3_CH7`/`PWR_VOLT`…）或项目层 `can(报文,信号)` |
| `kind` | `write` 写激励 / `fault` 故障注入 / `read` 采集 / `power` 电源 |
| `values` | 词→数值映射（如 请求三档→4）；或 `unit`（V/Ω/A，让 Excel 写数字） |
| `expect_key` | read 类：判定键（`hard`/`can`），与 `assert_outputs` 对应 |
| `verify` | 判定语义：默认 `eq`（EQ 等值，与现有实证一致） |
| `companion` | fault 配合对（如 输出短地 = CH1=1 + CH10=2），生成器整对翻译 |
| `reset` | 是否进用例前后复位（相应条目会自动进 module.yaml 的 reset 段校验） |

示例（直接用 left_heating 现有事实，等价现有模块层配置）：

```yaml
module: left_heating
signals:
  加热请求:
    channel: can(HU_SEATSET_3F4_Msg, HU_DrvSeatHeat)
    kind: write
    values: {OFF: 1, 一档: 2, 二档: 3, 三档: 4, 无请求: 0}   # 0≠OFF,实证编码
  加热输出硬线: {channel: HW_DI0, kind: read, expect_key: hard, verify: eq}
  加热输出CAN:  {channel: CAN_SEAT_993_IndicatorDrvSeatHeat, kind: read, expect_key: can, verify: eq}
  NTC阻值:      {channel: RT_RES2, kind: write, unit: ohm}
  加热开关:     {channel: RT_DO0, kind: write, values: {按下: 1, 松开: 0}}
  NTC短地:      {channel: FIU3_CH7, kind: fault, value: 14}
  NTC短电源:    {channel: FIU3_CH7, kind: fault, value: 12}
  NTC开路:      {channel: FIU3_CH7, kind: fault, value: 8}
  输出短地:
    channel: FIU1_CH1
    kind: fault
    value: 1
    companion: {channel: FIU1_CH10, value: 2}      # 存量短地配合对(CH10 泄漏已修)
  输出开路:     {channel: FIU1_CH1, kind: fault, value: 2}
  电源电压:     {channel: PWR_VOLT, kind: power, unit: V}
  点火:         {channel: IGN, kind: write, values: {有效: 1, 无效: 0}}
```

> 这就是"下次给配置文件"的正面回答：**给的是词汇表，不是通道清单**——词汇表里才有通道，
> 且它由你们（懂台架的人）一次性确认，测试员此后只写 Excel 功能语言。

## 4. Excel 模板（固定列，测试员遵循）

| 列 | 必填 | 说明 |
|---|---|---|
| 用例号 | ✅ | 决定生成函数名 `test_<用例号>_<拼音>` 与报告排序（沿用"序号=执行序"规则） |
| 用例标题 | ✅ | 进 Allure 标题（零填充序号前缀规则随之生效） |
| 步骤号 | ✅ | 同用例内顺序；生成器按步号排序 |
| 动作 | ✅ | **必须是 bindings 里注册的词汇**，如 "设置NTC短地"/"请求三档加热" |
| 参数 | 视动作 | 数字（带单位的电源/阻值）或词汇表中登记的档位词 |
| 等待(s) | 视动作 | 纯数字；"等待"行可只有此列 |
| 期望（键=值） | 视用例 | 判定行：`加热输出硬线=0; 加热输出CAN=1`，键也必须是 read 类词汇 |
| 备注 | 否 | 原样写入 docstring/注释（可放评审结论、缺陷编号） |

规则（生成器强制，违规即报错并指出 Excel 行列号）：
- 动作/期望词未注册 → **fail fast**（列出词+行号），不是静默跳过；
- 同一用例内"注入故障"必须有对应"清除"（除末步由 teardown 兜底）——结构校验；
- 期望值写成词（如"被抑制"）时，必须在 bindings 的 `values` 里有映射，否则要求写数字；
- 判定语义默认 EQ；若某用例需要区间，显式 `期望: hard∈[0,1]` 并进 manifest 标注意事项（不静默放宽）。

## 5. 生成器：`tools/gen_from_excel.py`（复用现有内核）

- **复用**（不改）：单文件草稿/序号规则、`render_function` 的 assert EQ 模板、Allure 装饰、
  未映射通道草稿、manifest 结构；`gen_tests.py` 中的塌缩规则（档位请求 4 步→`request_heat`）保留为
  "词级快捷方式"（假设某项目 verbatim 沿用旧时序，通过 bindings 的 `preset: request_heat` 显式启用）。
- **新增**：Excel 解析 + bindings 校验 + 两级通道存在性检查（见 §6）+ 结构校验（§4）。
- **xlsx 读取**：台架机**无 openpyxl/pandas**且网络不稳 → 用**标准库**解析（xlsx 是 zip+XML：
  `sharedStrings.xml` + `sheet1.xml`，约 80 行；支持合并单元格取值、跳过空行）；CSV(UTF-8) 兜底。
  **不新增第三方依赖**。
- 输出与现有生成器同构，`compare_draft.py` 可直接对账（轨迹语义比对，已支持签名绑定/默认值）。

## 6. 两级校验（fail fast，防"跑错台架/通道不存在"）

1. **词汇↔通道**：bindings 里的 `channel` 必须在 `bench_io/registry.csv`（或项目层 CAN 矩阵清单）存在；
2. **Excel↔词汇**：Excel 每个动作/期望词都能在 bindings 找到；
3. **通道↔sdf**：可选深度校验——用 `tools/analyze_sdf.py` 对当前项目 sdf 重提一次，
   确认本次用例涉及的所有通道都在登记表里（防 sdf 版本漂移；即交接 P1 的"启动通道校验"）。

## 7. 与现有资产的关系

| 现有 | 变化 |
|---|---|
| `gen_tests.py`（.seq→草稿） | 保留（存量迁移仍有价值）；渲染内核抽出为公共函数供新生成器调用 |
| `bindings.yaml` vs 模块 `channels.py` | **同源**：bindings 是人读/生成的入口，channels.py 是代码消费端；生成器校验两者一致（或由 bindings 直接生成 channels.py，二选一，见 D4） |
| 用例拆分规则 | 沿用：一行用例号 = 一个独立 test 函数，禁止参数化合并 |
| 报告顺序 | 沿用：标题零填充序号前缀，禁 epic/feature/story 分组 |

## 8. 实施步骤（评审通过后，预计 1~2 轮会话）

1. `tools/xlsx_lite.py`（stdlib xlsx 读取）+ 单测（含合并单元格/空行/中文字符串）
2. `bindings.yaml` schema 校验器 + left_heating 的 bindings 全文（按现有代码事实回填）
3. `tools/gen_from_excel.py`：解析→校验→复用渲染内核→草稿+manifest
4. **基准回归**：把 left_heating 35 条用例按其语义写成一份 Excel 样表，
   生成草稿与现 `test_all.py` 用 `compare_draft.py` 对账，要求 **35/35**（已知偏差白名单沿用）
5. 模板交付：`docs/Excel用例模板.xlsx`（表头+填写说明+示例 3 条）
6. 下一个项目（C206-10）实战：填 bindings → 写首批 Excel 用例 → 生成→复核→上架

## 9. 决策点（请拍板）

| # | 决策 | 建议 |
|---|---|---|
| D1 | 绑定配置载体：`bindings.yaml`（人读） / 直接扩 `module.yaml` / Excel 另页 | **独立 `bindings.yaml`**（职责单一、可 diff、可签核；module.yaml 保持元信息） |
| D2 | Excel 输入：xlsx 直读（标准库） / 只收 CSV | **xlsx 直读 + CSV 兜底**（测试员不会为程序转格式） |
| D3 | 期望值写法：词（"被抑制"） / 一律数字 / 两者均可 | **两者均可，词必须在 bindings 注册**（测试员友好且可校验） |
| D4 | bindings 与模块 `channels.py` 关系：双份一致性校验 / bindings 为唯一源自动生成 channels.py | **bindings 为唯一源**（生成 `channels.py` 的常量段；减少漂移面）——若你担心生成代码不可读，退回"双份+校验" |
| D5 | 词汇表由谁签核 | **你/台架负责人**签一次；测试员后续只写 Excel（本方案的收益点） |
| D6 | 新项目是否强制走 sdf 深度校验 | 建议强制（P1 待办"启动通道校验"顺带闭环） |

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| Excel 表格结构被改乱（加列/合并） | 模板锁定 + 生成器报行号级错误；表头不匹配直接拒绝 |
| 词汇表膨胀/同义词乱写 | 生成器做"近义词未注册"提示（如出现"三档"而只注册"请求三档"）；词汇表纳入评审 |
| xlsx 标准库解析边角（富文本/公式/多 sheet） | 只用第一个 sheet + 取值公式结果；富文本取纯文本；样表回归覆盖 |
| 误把功能词当通道（历史 .seq 思维） | 本方案物理上不允许 Excel 写通道；通道只存在于 bindings |
| 判定语义被静默放宽 | 默认 EQ；区间/容差需显式写法并进 manifest |
