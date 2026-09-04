"""
Mifare Classic MFD文件解析器
用于解析.mfd文件并提取扇区数据
"""

import os
from typing import List, Dict, Optional, Tuple


def decode_mifare_access_bits(trailer: bytes) -> dict:
    """解析 MIFARE Classic 尾块的访问控制位。

    移植自 libfreefare mifare_classic.c:590-624,适配 Python。
    包含反码校验,损坏的尾块会抛出 ValueError。

    Returns:
      {
        "valid": True,
        "access_bytes": bytes[3],   # 原 bytes[6:9]
        "gpb": int,                  # byte[9]
        "c1_nibble": int,            # C1 的 4-bit
        "c2_nibble": int,            # C2 的 4-bit
        "c3_nibble": int,            # C3 的 4-bit
        "normal": int,               # 12-bit normal value
        "inverted": int,             # 12-bit inverted value
      }
    """
    if len(trailer) != 16:
        raise ValueError("尾块必须为 16 字节")
    b6, b7, b8 = trailer[6], trailer[7], trailer[8]
    inverted = b6 | ((b7 & 0x0F) << 8) | 0xF000
    normal = ((b7 & 0xF0) >> 4) | (b8 << 4)
    if normal != ((~inverted) & 0xFFFF):
        raise ValueError("访问控制位反码校验失败(尾块可能损坏)")
    return {
        "valid": True,
        "access_bytes": bytes([b6, b7, b8]),
        "gpb": trailer[9],
        "c1_nibble": normal & 0x0F,
        "c2_nibble": (normal >> 4) & 0x0F,
        "c3_nibble": (normal >> 8) & 0x0F,
        "normal": normal & 0xFFF,
        "inverted": inverted & 0xFFF,
    }


def access_shift_for_block(block: int) -> int:
    """给定 block 号,返回它对应的 access slot 索引(0-3)。"""
    if block < 128:
        return block % 4
    return ((block - 128) % 16) // 5


def access_condition_for_block(block: int, trailer_block: int, normal: int) -> int:
    """计算某 block 的 C1/C2/C3 (3 bit 索引 0-7)。"""
    if block == trailer_block:
        shift = 3
    else:
        shift = access_shift_for_block(block)
    c1 = (normal >> shift) & 0x01
    c2 = (normal >> (4 + shift)) & 0x01
    c3 = (normal >> (8 + shift)) & 0x01
    return c1 | (c2 << 1) | (c3 << 2)


# 移植自 libfreefare mifare_data_access_permissions[8] (mifare_classic.c:115-137)
# 高 4 位:Key A 权限 (R/W/D/I),低 4 位:Key B 权限
# bit: R=0x8, W=0x4, D=0x2(decrement), I=0x1(increment)
_DATA_PERM = [
    0xff,  # 000: default (KeyA: RWDI, KeyB: RWDI)
    0x8c,  # 001
    0x88,  # 010
    0xaf,  # 011
    0xaa,  # 100
    0x08,  # 101
    0x0c,  # 110
    0x00,  # 111 (no access)
]

# Trailer block 权限表 (mifare_classic.c:139-166)
# 高位:Key A,低位:Key B;位:READ_KEYA=0x400, WRITE_KEYA=0x100,
# READ_ACCESS=0x040, WRITE_ACCESS=0x010, READ_KEYB=0x004, WRITE_KEYB=0x001
_TRAILER_PERM = [
    0x28a,  # 000 (default)
    0x1c1,
    0x088,
    0x0c0,
    0x2aa,
    0x0d0,
    0x1d1,
    0x0c0,
]


def get_data_block_permission(condition: int, key_type: str = "A") -> dict:
    """数据块权限查询。condition 是 C1/C2/C3 索引 0-7,key_type 是 'A' 或 'B'。

    Returns: {"R": bool, "W": bool, "D": bool, "I": bool}
    """
    if not 0 <= condition <= 7:
        return {"R": False, "W": False, "D": False, "I": False}
    shift = 4 if key_type.upper() == "A" else 0
    perm_byte = (_DATA_PERM[condition] >> shift) & 0x0F
    return {
        "R": bool(perm_byte & 0x8),
        "W": bool(perm_byte & 0x4),
        "D": bool(perm_byte & 0x2),
        "I": bool(perm_byte & 0x1),
    }


def get_trailer_block_permission(condition: int, key_type: str = "A") -> dict:
    """Trailer 块权限查询。"""
    if not 0 <= condition <= 7:
        return {"READ_KEYA": False, "WRITE_KEYA": False,
                "READ_ACCESS_BITS": False, "WRITE_ACCESS_BITS": False,
                "READ_KEYB": False, "WRITE_KEYB": False}
    shift = 1 if key_type.upper() == "A" else 0
    perm = (_TRAILER_PERM[condition] >> shift) & 0x1FF
    return {
        "READ_KEYA": bool(perm & 0x400),
        "WRITE_KEYA": bool(perm & 0x100),
        "READ_ACCESS_BITS": bool(perm & 0x040),
        "WRITE_ACCESS_BITS": bool(perm & 0x010),
        "READ_KEYB": bool(perm & 0x004),
        "WRITE_KEYB": bool(perm & 0x001),
    }


def format_data_perm(perm: dict) -> str:
    return f"{'R' if perm['R'] else '-'}{'W' if perm['W'] else '-'}{'D' if perm['D'] else '-'}{'I' if perm['I'] else '-'}"


def format_trailer_perm(perm: dict) -> str:
    return (f"rKA={'Y' if perm['READ_KEYA'] else 'N'} "
            f"wKA={'Y' if perm['WRITE_KEYA'] else 'N'} "
            f"rAB={'Y' if perm['READ_ACCESS_BITS'] else 'N'} "
            f"wAB={'Y' if perm['WRITE_ACCESS_BITS'] else 'N'} "
            f"rKB={'Y' if perm['READ_KEYB'] else 'N'} "
            f"wKB={'Y' if perm['WRITE_KEYB'] else 'N'}")


class MifareClassicSector:
    """Mifare Classic扇区数据类"""

    def __init__(self, sector_num: int):
        self.sector_num = sector_num
        self.blocks = []  # 存储该扇区的所有块数据
        self.key_a = None  # Key A
        self.key_b = None  # Key B
        self.access_bits = None  # 访问控制位(3 bytes,hex)
        self.gpb = None  # General Purpose Byte (trailer[9])
        self.access_decoded = None  # dict from decode_mifare_access_bits()

    def add_block(self, block_num: int, data: bytes):
        """添加块数据"""
        self.blocks.append({
            'block_num': block_num,
            'data': data,
            'hex_data': data.hex().upper()
        })

    def set_keys_and_access(self, key_a: bytes, access_bits: bytes, key_b: bytes):
        """设置密钥和访问控制位。

        access_bits 接受 3 或 4 字节:
          - 3 字节 (trailer[6:9]): 标准 MIFARE access bits
          - 4 字节 (trailer[6:10]): 含 GPB,自动拆分
        """
        self.key_a = key_a.hex().upper() if key_a else None
        self.key_b = key_b.hex().upper() if key_b else None
        if access_bits is None:
            self.access_bits = None
            self.gpb = None
            self.access_decoded = None
            return
        if len(access_bits) == 4:
            self.access_bits = access_bits[:3].hex().upper()
            self.gpb = access_bits[3]
        else:
            self.access_bits = access_bits.hex().upper()
            self.gpb = None
        # 自动解析 (忽略解析失败,access_decoded 保持 None)
        try:
            trailer = (key_a or b'') + access_bits[:3] + bytes([self.gpb or 0]) + (key_b or b'')
            if len(trailer) == 16:
                self.access_decoded = decode_mifare_access_bits(trailer)
        except (ValueError, Exception):
            self.access_decoded = None
        



class MFDParser:
    """MFD文件解析器"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.sectors = []
        self.card_type = None
        self.total_sectors = 0
        
    def parse_mfd_file(self, file_path: str = None) -> bool:
        """
        解析MFD文件
        
        Args:
            file_path: MFD文件路径，如果为None则使用初始化时的路径
            
        Returns:
            bool: 解析是否成功
        """
        try:
            # 如果没有提供file_path，使用初始化时的路径
            if file_path is None:
                file_path = self.file_path
                
            if not os.path.exists(file_path):
                return False
                
            with open(file_path, 'rb') as f:
                data = f.read()
                
            # 检查文件大小来确定卡类型
            file_size = len(data)
            if file_size == 1024:  # 1K卡
                self.card_type = "Mifare Classic 1K"
                self.total_sectors = 16
                return self._parse_1k_card(data)
            elif file_size == 4096:  # 4K卡
                self.card_type = "Mifare Classic 4K"
                self.total_sectors = 40
                return self._parse_4k_card(data)
            else:
                return False
                
        except Exception as e:
            print(f"解析MFD文件时出错: {e}")
            return False
            
    def _parse_1k_card(self, data: bytes) -> bool:
        """解析1K卡数据"""
        try:
            self.sectors = []
            
            # 1K卡有16个扇区，每个扇区4个块，每个块16字节
            for sector_num in range(16):
                sector = MifareClassicSector(sector_num)
                
                # 每个扇区的起始位置
                sector_start = sector_num * 64  # 4块 * 16字节
                
                # 读取前3个数据块
                for block_in_sector in range(3):
                    block_start = sector_start + (block_in_sector * 16)
                    block_data = data[block_start:block_start + 16]
                    global_block_num = sector_num * 4 + block_in_sector
                    sector.add_block(global_block_num, block_data)
                
                # 读取尾块（包含密钥和访问控制位）
                trailer_start = sector_start + 48  # 第4个块
                trailer_data = data[trailer_start:trailer_start + 16]
                
                # 解析尾块：Key A (6字节) + 访问控制位 (4字节) + Key B (6字节)
                key_a = trailer_data[0:6]
                access_bits = trailer_data[6:10]
                key_b = trailer_data[10:16]
                
                sector.set_keys_and_access(key_a, access_bits, key_b)
                
                # 添加尾块到块列表
                global_trailer_num = sector_num * 4 + 3
                sector.add_block(global_trailer_num, trailer_data)
                
                self.sectors.append(sector)
                
            return True
            
        except Exception as e:
            print(f"解析1K卡数据时出错: {e}")
            return False
            
    def _parse_4k_card(self, data: bytes) -> bool:
        """解析4K卡数据"""
        try:
            self.sectors = []
            
            # 4K卡：前32个扇区每个4块，后8个扇区每个16块
            block_offset = 0
            
            # 前32个扇区（每个扇区4个块）
            for sector_num in range(32):
                sector = MifareClassicSector(sector_num)
                
                # 读取前3个数据块
                for block_in_sector in range(3):
                    block_data = data[block_offset:block_offset + 16]
                    sector.add_block(block_offset // 16, block_data)
                    block_offset += 16
                
                # 读取尾块
                trailer_data = data[block_offset:block_offset + 16]
                key_a = trailer_data[0:6]
                access_bits = trailer_data[6:10]
                key_b = trailer_data[10:16]
                
                sector.set_keys_and_access(key_a, access_bits, key_b)
                sector.add_block(block_offset // 16, trailer_data)
                block_offset += 16
                
                self.sectors.append(sector)
            
            # 后8个扇区（每个扇区16个块）
            for sector_num in range(32, 40):
                sector = MifareClassicSector(sector_num)
                
                # 读取前15个数据块
                for block_in_sector in range(15):
                    block_data = data[block_offset:block_offset + 16]
                    sector.add_block(block_offset // 16, block_data)
                    block_offset += 16
                
                # 读取尾块
                trailer_data = data[block_offset:block_offset + 16]
                key_a = trailer_data[0:6]
                access_bits = trailer_data[6:10]
                key_b = trailer_data[10:16]
                
                sector.set_keys_and_access(key_a, access_bits, key_b)
                sector.add_block(block_offset // 16, trailer_data)
                block_offset += 16
                
                self.sectors.append(sector)
                
            return True
            
        except Exception as e:
            print(f"解析4K卡数据时出错: {e}")
            return False
            
    def get_sectors_data(self) -> List[Dict]:
        """获取所有扇区的数据"""
        return [{
            'sector_num': sector.sector_num,
            'key_a': sector.key_a,
            'key_b': sector.key_b,
            'access_bits': sector.access_bits,
            'gpb': sector.gpb,
            'access_decoded': sector.access_decoded,
            'blocks': sector.blocks,
            'block_count': len(sector.blocks)
        } for sector in self.sectors]
        
    def get_sector_count(self) -> int:
        """获取扇区总数"""
        return len(self.sectors)
        
    def get_card_info(self) -> Dict:
        """获取卡片信息"""
        return {
            'card_type': self.card_type,
            'total_sectors': self.total_sectors,
            'parsed_sectors': len(self.sectors)
        }
        
    def export_to_text(self, output_path: str) -> bool:
        """导出扇区数据到文本文件"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"卡片类型: {self.card_type}\n")
                f.write(f"扇区总数: {self.total_sectors}\n")
                f.write("=" * 50 + "\n\n")
                
                for sector in self.sectors:
                    f.write(f"扇区 {sector.sector_num}:\n")
                    f.write(f"  Key A: {sector.key_a}\n")
                    f.write(f"  Key B: {sector.key_b}\n")
                    f.write(f"  访问控制位: {sector.access_bits}\n")
                    f.write("  块数据:\n")
                    
                    for block in sector.blocks:
                        f.write(f"    块 {block['block_num']}: {block['hex_data']}\n")
                    
                    f.write("\n")
                    
            return True
            
        except Exception as e:
            print(f"导出文本文件时出错: {e}")
            return False


# 测试函数
def test_mfd_parser():
    """测试MFD解析器"""
    parser = MFDParser("")
    
    # 查找测试文件 - 使用 PathManager 获取跨平台路径
    from path_manager import PathManager
    test_file = os.path.join(PathManager.get_nfc_bin_dir(), "20251009_224038.mfd")
    if os.path.exists(test_file):
        print(f"测试文件: {test_file}")
        
        if parser.parse_mfd_file(test_file):
            print("解析成功!")
            card_info = parser.get_card_info()
            print(f"卡片信息: {card_info}")
            
            sectors_data = parser.get_sectors_data()
            print(f"解析到 {len(sectors_data)} 个扇区")
            
            # 显示前几个扇区的信息
            for i, sector in enumerate(sectors_data[:3]):
                print(f"\n扇区 {sector['sector_num']}:")
                print(f"  Key A: {sector['key_a']}")
                print(f"  Key B: {sector['key_b']}")
                print(f"  块数量: {sector['block_count']}")
        else:
            print("解析失败!")
    else:
        print(f"测试文件不存在: {test_file}")


if __name__ == "__main__":
    test_mfd_parser()