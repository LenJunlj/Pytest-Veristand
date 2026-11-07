# -*- coding: utf-8 -*-
"""台架层通道 —— 同台架所有项目共用(docs/通道分层方案.md D1/D2,2026-11-07)

本文件只装"台架硬件事实",不含任何车型/模块语义:

- **模型参数相对标识**:前斜杠、不含模型前缀(即 .../Models/<模型>/Parameters/ 之后的部分)。
  由项目层 channels.bench(rel) 拼全路径 —— 换项目只换前缀,本文件不动。
- **DAQ 硬件通道**:目标级全路径(无模型前缀),原样使用。
- **CAN1 内部总线设备**(FIU×3 板 / RES×3 板 / 程控电源 PowerSupply(257) / 电流采集 /
  SW7F 原始帧)不在此出常量:测试一律经模型参数层驱动,设备拓扑与报文明细见 registry.csv。

实证依据(tools/analyze_sdf.py,双项目 diff,docs/通道分层方案.md §7.2):
p2546 与 C026-10 的电源/FIU/硬线路由/DAQ Dev1/Dev2 逐项一致,项目层 CAN 矩阵零交集。

命名注意:
- "VlotageControl" 是模型原始拼写(少 e),照抄以匹配真实通道;
- "ON//OFF" 的双斜杠是 VeriStand 对名字内斜杠的转义,原样保留;
- DI 跨 port0/1/2,编号非连续(如 DI8 在 port2),照抄 sdf,勿公式化。
"""

# ---- 电源(程控电源,经模型参数层下发,CAN1 PowerSupply(257);sdf 限幅 0~20V / 0~25A) ----
PWR_VOLT = "IO/PowerControl/VlotageControl/Value"      # 原文拼写少 e
PWR_CURR = "IO/PowerControl/CurrentControl/Value"
PWR_ON = "IO/PowerControl/ON//OFF/Value"               # 名字含斜杠,VeriStand // 转义
PWR_RELAY = "IO/PowerControl/Power_Relay/Value"
IGN = "IO/PowerControl/IGN/Value"

# ---- FIU 故障注入通道本体(3 板 × 10 路;注入"值域"是模块层事实) ----


def _fiu(board, ch):
    pfx = {1: "FIU1OUT", 2: "FIU2_OUT", 3: "FIU3_OUT"}[board]
    return "IO/FIU/%s_Channel%d/Value" % (pfx, ch)


# 全集键形如 "3_CH7";板卡控制通道(FIU*_CH/Fuction/ctrl)不入此字典(用例不写)
FIU = {"%d_CH%d" % (b, c): _fiu(b, c) for b in (1, 2, 3) for c in range(1, 11)}

# 现用别名(left_heating;新模块按需增别名或用 FIU[...])
FIU1_CH1 = FIU["1_CH1"]
FIU1_CH10 = FIU["1_CH10"]
FIU3_CH7 = FIU["3_CH7"]
FIU3_CH9 = FIU["3_CH9"]

# ---- 硬线信号路由(HardLine IO Model;DO/AO/PO 输出与 RES 电阻仿真) ----
_RT = "IO/HardLine IO Model/MDLDataToController/MDLSignalRouting/%s/Value"
SIGNAL_ROUTING = {}
for _fam, _n in (("DO", 24), ("AO", 4), ("PO", 4), ("RES", 24)):
    for _i in range(_n):
        _name = "%s%d" % (_fam, _i)
        SIGNAL_ROUTING[_name] = _RT % _name

# 现用别名;RES 三块板路由:RES10_CH1~8←RES0~7、RES18_CH1~8←RES8~15、RES20_CH1~8←RES16~23
# (参数值 ×2 下发板卡,CAN1 Event Triggered)
RT_DO0 = SIGNAL_ROUTING["DO0"]
RT_RES2 = SIGNAL_ROUTING["RES2"]

# --- 生成区:DAQ Dev1 全 84 条(照抄 sdf,DI 跨 port0/1/2 编号非连续) ---
DAQ = {
    "AI0": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI0",
    "AI1": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI1",
    "AI2": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI2",
    "AI3": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI3",
    "AI4": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI4",
    "AI5": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI5",
    "AI6": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI6",
    "AI7": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI7",
    "AI8": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI8",
    "AI9": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI9",
    "AI10": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI10",
    "AI11": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI11",
    "AI12": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI12",
    "AI13": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI13",
    "AI14": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI14",
    "AI15": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI15",
    "AI16": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI16",
    "AI17": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI17",
    "AI18": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI18",
    "AI19": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI19",
    "AI20": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI20",
    "AI21": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI21",
    "AI22": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI22",
    "AI23": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI23",
    "AI24": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI24",
    "AI25": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI25",
    "AI26": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI26",
    "AI27": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI27",
    "AI28": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI28",
    "AI29": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI29",
    "AI30": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI30",
    "AI31": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Input/AI31",
    "AO0": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Output/AO0",
    "AO1": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Output/AO1",
    "AO2": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Output/AO2",
    "AO3": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Analog Output/AO3",
    "DI0": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI0",
    "DI1": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI1",
    "DI2": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI2",
    "DI3": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI3",
    "DI4": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI4",
    "DI5": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI5",
    "DI6": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI6",
    "DI7": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port0/DI7",
    "DI8": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI8",
    "DI9": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI9",
    "DI10": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI10",
    "DI11": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI11",
    "DI12": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI12",
    "DI13": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI13",
    "DI14": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI14",
    "DI15": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI15",
    "DI16": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI16",
    "DI17": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI17",
    "DI18": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI18",
    "DI19": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port1/DI19",
    "DI20": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI20",
    "DI21": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI21",
    "DI22": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI22",
    "DI23": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Input/port2/DI23",
    "DO0": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO0",
    "DO1": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO1",
    "DO2": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO2",
    "DO3": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO3",
    "DO4": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO4",
    "DO5": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO5",
    "DO6": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO6",
    "DO7": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO7",
    "DO8": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO8",
    "DO9": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO9",
    "DO10": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO10",
    "DO11": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO11",
    "DO12": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO12",
    "DO13": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO13",
    "DO14": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO14",
    "DO15": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO15",
    "DO16": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO16",
    "DO17": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO17",
    "DO18": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO18",
    "DO19": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO19",
    "DO20": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO20",
    "DO21": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO21",
    "DO22": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO22",
    "DO23": "Targets/Controller/Hardware/Chassis/DAQ/Dev1/Digital Output/port0/DO23",
}

# 现用别名
HW_DI0 = DAQ["DI0"]
