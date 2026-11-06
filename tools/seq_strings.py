# -*- coding: utf-8 -*-
"""从 TestStand 二进制 .seq（TOF 格式）中提取可读字符串 —— 应急盘点用。

背景：TestStand 保存 .seq 默认是二进制 TOF 格式（文件头 TOF1），不是 XML。
完整可靠的结构化解析必须回到装了 TestStand 的机器上把它转成 XML/文本格式。
本脚本只做字符串级挖掘：步骤名、通道别名（Aliases/...）、表达式等通常明文存储，
足够产出【初步】迁移清单，但不保证捕获全部结构与执行顺序。

用法：
    python tools/seq_strings.py samples/xxx.seq [--all]
    默认只显示"关键行"（含 Aliases/Locals/Step/Seq 等关键词），--all 显示全部。
"""
import argparse
import re
import sys

KEYWORDS = ("Aliases", "Locals.", "FileGlobals.", "Parameters.", "Step.", "Sequence",
            "Expr", "Limit", "nivssdf", "VeriStand", ".seq", "Property", "Targets\\")


def load_payload(path: str) -> bytes:
    """读 .seq；若是 TestStand 二进制 TOF 格式（文件头 TOF1），自动定位并解压 zlib 负载。

    实证：TOF = 头部 + zlib 压缩的属性流（属性树为二进制，字符串集中在尾部字符串表）。
    """
    import zlib
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(b"TOF"):
        return data          # 文本/XML 格式，原样返回
    for off in range(len(data) - 1):
        if data[off] == 0x78 and data[off + 1] in (0x01, 0x5E, 0x9C, 0xDA):
            try:
                out = zlib.decompressobj().decompress(data[off:])
            except Exception:
                continue
            if len(out) > 200:
                print(f"[TOF] 已自动解压 zlib 负载 @0x{off:x}: {len(data)} -> {len(out)} 字节")
                return out
    raise RuntimeError(f"{path}: TOF 格式但未找到 zlib 负载")


def ascii_runs(data: bytes, minlen=4):
    pat = rb"[\x20-\x7e]{%d,}" % minlen
    for m in re.finditer(pat, data):
        yield m.start(), m.group().decode("ascii", "replace")


def utf16le_runs(data: bytes, minlen=4):
    pat = rb"(?:[\x20-\x7e]\x00){%d,}" % minlen
    for m in re.finditer(pat, data):
        yield m.start(), m.group().decode("utf-16-le", "replace")


def gbk_runs(data: bytes, minlen=2):
    """含 GBK 双字节字符的串（中文步骤名等）。只保留确实含双字节的，纯 ASCII 由上面覆盖。"""
    pat = rb"(?:[\x20-\x7e]|[\x81-\xfe][\x40-\xfe]){%d,}" % (minlen * 2)
    for m in re.finditer(pat, data):
        raw = m.group()
        if re.search(rb"[\x81-\xfe]", raw):
            try:
                yield m.start(), raw.decode("gbk", "strict")
            except UnicodeDecodeError:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("seq")
    ap.add_argument("--all", action="store_true", help="显示全部字符串（默认只显示关键行）")
    args = ap.parse_args()

    with open(args.seq, "rb") as f:
        pass  # 占位，实际读取在 load_payload 中完成

    data = load_payload(args.seq)

    runs = []
    runs += [(off, "A", s) for off, s in ascii_runs(data)]
    runs += [(off, "U", s) for off, s in utf16le_runs(data)]
    runs += [(off, "G", s) for off, s in gbk_runs(data)]
    runs.sort(key=lambda x: (x[0], x[1]))

    print(f"文件: {args.seq}  大小: {len(data)} 字节  提取字符串: {len(runs)} 条")

    shown = 0
    for off, kind, s in runs:
        s_show = s.strip()
        if not s_show:
            continue
        is_key = any(k.lower() in s_show.lower() for k in KEYWORDS)
        if args.all or is_key:
            print(f"{off:08x} [{kind}] {s_show}")
            shown += 1
    if not args.all:
        print(f"（仅显示关键行 {shown} 条；--all 查看全部 {len(runs)} 条）")


if __name__ == "__main__":
    sys.exit(main())
