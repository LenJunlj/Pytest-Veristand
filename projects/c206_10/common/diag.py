# -*- coding: utf-8 -*-
"""C206-10 诊断（UDS over CAN）—— 原封翻译存量 TestStand Python 步骤。

原文（功能DTC测试.seq）两步 Python 调用：
    clear_dtc(diag_request_id="762")                              → 清故障码
    checkdtc(diag_request_id="762", diag_response_id="76A",
             be_checked_dtc="90E017")                             → 返回 'True'/'False'
实现来源：F:\\TongYuTestScript\\Lib\\site-packages\\customLib\\Check_DTC1.py（台架现场验证过），
本文件按同一报文时序复刻，去掉对 site-packages 绝对路径的依赖：
    19 02 09 请求读 DTC → 收到首帧(0x1X)回 30 00 连续帧流控 → 收齐后按 4 字节/条解析，
    状态字节 == 0x09（本次操作循环故障）才算 True。
判定阈值：原文 String Limit —— Limits.String = "True"/"False"，Comp = IgnoreCase。

硬件：PCAN-USB（PCAN_USBBUS1, 500k），与 TestStand 时代一致；不是 VeriStand 的 CAN2。
"""
import threading
import time

try:
    import can
except Exception:                        # 无 python-can 时让导入本身成功，用例里 skip
    can = None

DEFAULT_CHANNEL = "PCAN_USBBUS1"
DEFAULT_BITRATE = 500000
RX_WINDOW_S = 0.1        # 原文 threading.Timer(0.1, timer)
DTC_STATUS_FAILED = 0x09  # 原文 statusbit = '09'


def _bus(channel=DEFAULT_CHANNEL, bitrate=DEFAULT_BITRATE):
    if can is None:
        raise RuntimeError("未安装 python-can，DTC 用例无法执行")
    return can.ThreadSafeBus(bustype="pcan", channel=channel, bitrate=bitrate)


def clear_dtc(diag_request_id: str):
    """原文 clear_dtc：发 04 14 FF FF FF（UDS ClearDiagnosticInformation，全组）。"""
    bus = _bus()
    try:
        bus.send(can.Message(arbitration_id=int(diag_request_id, 16),
                             data=[0x04, 0x14, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00],
                             is_extended_id=False))
    finally:
        bus.shutdown()
    return "OK"


def check_dtc(diag_request_id: str, diag_response_id: str, be_checked_dtc: str):
    """原文 checkdtc：读 DTC 列表，返回 'True'（存在且状态=0x09）/ 'False'（不存在或未确认）。"""
    req_id, resp_id = int(diag_request_id, 16), int(diag_response_id, 16)
    checked = be_checked_dtc.lower()
    bus = _bus()
    rx = {"on": True}
    threading.Timer(RX_WINDOW_S, lambda: rx.update(on=False)).start()
    buf, total = [], 0
    flow = can.Message(arbitration_id=req_id,
                       data=[0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                       is_extended_id=False)
    try:
        bus.send(can.Message(arbitration_id=req_id,
                             data=[0x03, 0x19, 0x02, 0x09, 0x00, 0x00, 0x00, 0x00],
                             is_extended_id=False))
        while rx["on"]:
            msg = bus.recv(timeout=0.05)
            if msg is None or msg.arbitration_id != resp_id:
                continue
            d = msg.data
            if d[0] & 0xF0 == 0x10:            # 首帧：长度在高 4 位 + 低 4 位
                total = ((d[0] << 8) + d[1]) & 0x0FFF
                buf.extend(d[5:8])
                bus.send(flow)
            elif d[0] & 0xF0 == 0x00:          # 单帧
                total = d[0] & 0x0F
                buf.extend(d[4:8])
            elif d[0] & 0xF0 == 0x20:          # 连续帧
                buf.extend(d[1:8])
    finally:
        bus.shutdown()

    # 原文的裁剪逻辑：只保留 total-3 字节（DTC 记录 4 字节/条，去掉 59 02 09 头）
    keep = len(buf) - (total - 3)
    if keep > 0:
        del buf[-keep:]
    dtcs = []
    for i in range(0, len(buf) - 3, 4):
        code = (buf[i] << 16) + (buf[i + 1] << 8) + buf[i + 2]
        dtcs.append(("%06x" % code, buf[i + 3]))

    for code, status in dtcs:
        if code == checked:
            return "True" if status == DTC_STATUS_FAILED else "False"
    return "False"
