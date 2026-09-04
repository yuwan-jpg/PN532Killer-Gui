"""
卡类型指纹数据库。
基于 SAK + ATQA + UID 长度识别已知卡片变体。
参考 nfc-tools/libnfc + libfreefare freefare.c + NXP AN10833。
"""

from typing import Dict, Optional, Tuple


# SAK 值定义
SAK_ULTRALIGHT = 0x00
SAK_MIFARE_CLASSIC_1K = 0x08
SAK_MIFARE_CLASSIC_MINI = 0x09
SAK_MIFARE_PLUS_2K = 0x10
SAK_MIFARE_PLUS_4K = 0x11
SAK_MIFARE_PLUS_S = 0x20
SAK_MIFARE_CLASSIC_4K = 0x18
SAK_ISO15693 = 0x40
SAK_NTAG = 0x00
SAK_DESFIRE = 0x20
SAK_FELICA = 0x01


# (SAK, ATQA 高字节, ATQA 低字节, UID 长度, 类别) -> 名称
_FINGERPRINTS: list = [
    # (sak, atqa_high, atqa_low, uid_len, name, gen)
    (0x00, 0x44, 0x00, 4, "MIFARE Ultralight", "MF0ICU1"),
    (0x00, 0x44, 0x00, 7, "MIFARE Ultralight EV1", "MF0UL11"),
    (0x00, 0x04, 0x00, 7, "NTAG213/215/216", "NTAG21x"),
    (0x00, 0x04, 0x03, 7, "NTAG213", "NTAG213"),
    (0x00, 0x04, 0x04, 7, "NTAG215", "NTAG215"),
    (0x00, 0x04, 0x05, 7, "NTAG216", "NTAG216"),
    (0x08, 0x04, 0x00, 4, "MIFARE Classic 1K (Gen1A/UID)", "CUID"),
    (0x08, 0x04, 0x00, 7, "MIFARE Classic 1K EV1", "MFC1K-EV1"),
    (0x09, 0x04, 0x00, 4, "MIFARE Mini", "MF MINI"),
    (0x18, 0x02, 0x00, 4, "MIFARE Classic 4K", "MFC4K"),
    (0x18, 0x02, 0x00, 7, "MIFARE Classic 4K EV1", "MFC4K-EV1"),
    (0x10, 0x04, 0x00, 4, "MIFARE Plus 2K (SL0)", "PLUS 2K"),
    (0x11, 0x04, 0x00, 4, "MIFARE Plus 4K (SL0)", "PLUS 4K"),
    (0x20, 0x04, 0x00, 7, "MIFARE Plus S 2K (SL1+)", "PLUS-S"),
    (0x20, 0x44, 0x00, 7, "MIFARE Plus S 4K (SL1+)", "PLUS-S 4K"),
    (0x20, 0x04, 0x03, 7, "MIFARE DESFire EV1", "DESFire-EV1"),
    (0x20, 0x04, 0x04, 7, "MIFARE DESFire EV2", "DESFire-EV2"),
    (0x20, 0x04, 0x05, 7, "MIFARE DESFire EV3", "DESFire-EV3"),
    # ISO15693
    (0x40, 0x01, 0x00, 8, "ISO15693 (NXP/STM)", "ISO15693"),
    (0x40, 0x04, 0x01, 8, "ISO15693 (T5557 后向兼容)", "ISO15693"),
]


def identify_card(sak: int, atqa: bytes, uid_len: int) -> Dict:
    """根据 SAK + ATQA + UID 长度返回最匹配的卡类型。

    返回:
      {
        "name": str,        # 卡名称
        "model": str,       # 内部型号代码
        "size": str,        # 容量 (1K/4K/NTAG...)
        "gen": str,         # 世系
        "confidence": str,  # "exact" | "partial" | "unknown"
      }
    """
    if isinstance(sak, bytes):
        sak = sak[0]
    atqa_b = bytes(atqa) if atqa else b''
    atqa_high = atqa_b[0] if len(atqa_b) > 0 else 0
    atqa_low = atqa_b[1] if len(atqa_b) > 1 else 0

    # 完全匹配
    for s, ah, al, ul, name, model in _FINGERPRINTS:
        if s == sak and ah == atqa_high and al == atqa_low and ul == uid_len:
            return {
                "name": name,
                "model": model,
                "size": _infer_size(name),
                "gen": _infer_gen(name),
                "confidence": "exact",
            }

    # 部分匹配(忽略 ATQA low)
    for s, ah, al, ul, name, model in _FINGERPRINTS:
        if s == sak and ah == atqa_high and ul == uid_len:
            return {
                "name": name,
                "model": model,
                "size": _infer_size(name),
                "gen": _infer_gen(name),
                "confidence": "partial",
            }

    # 仅 SAK + UID
    for s, ah, al, ul, name, model in _FINGERPRINTS:
        if s == sak and ul == uid_len:
            return {
                "name": name,
                "model": model,
                "size": _infer_size(name),
                "gen": _infer_gen(name),
                "confidence": "partial",
            }

    # 完全未知
    return {
        "name": "Unknown",
        "model": "Unknown",
        "size": "Unknown",
        "gen": "Unknown",
        "confidence": "unknown",
    }


def _infer_size(name: str) -> str:
    if "1K" in name: return "1KB"
    if "2K" in name: return "2KB"
    if "4K" in name: return "4KB"
    if "Mini" in name: return "320B"
    if "Ultralight" in name: return "640B"
    if "Ultralight EV1" in name or "NTAG" in name: return "1KB"
    if "DESFire" in name: return "8KB+"
    if "ISO15693" in name: return "≥1KB"
    return "Unknown"


def _infer_gen(name: str) -> str:
    """从名称推断世代。"""
    if "EV3" in name: return "Gen3"
    if "EV2" in name: return "Gen2"
    if "EV1" in name: return "Gen1"
    if "Plus" in name: return "Plus"
    if "DESFire" in name: return "EV1+/EV2/EV3"
    if "Mini" in name: return "Mini"
    return "Standard"


def get_sak_info(sak: int) -> Optional[Tuple[str, int]]:
    """返回 (卡类名, 块组大小)。"""
    if isinstance(sak, bytes):
        sak = sak[0]
    table = {
        0x00: ("MIFARE Ultralight / NTAG", 4),
        0x01: ("FeliCa", 0),
        0x08: ("MIFARE Classic 1K (CUID/UID/FUID)", 4),
        0x09: ("MIFARE Mini", 4),
        0x10: ("MIFARE Plus 2K", 4),
        0x11: ("MIFARE Plus 4K", 4),
        0x18: ("MIFARE Classic 4K", 4),
        0x20: ("MIFARE Plus / DESFire", 4),
        0x40: ("ISO15693", 0),
    }
    return table.get(sak)
