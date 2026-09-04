"""
嗅探数据解析模块
用于解析 MIFARE Classic 认证数据
"""

from pn532_enum import PN532KillerSnifferMode


class SnifferParser:
    """嗅探数据解析器"""
    
    @staticmethod
    def reverse_hex(h_str):
        """反转十六进制字符串的字节序"""
        return bytes.fromhex(h_str)[::-1].hex()
    
    @staticmethod
    def parse_sniffer_auth_data(all_data: bytes, sniff_mode: PN532KillerSnifferMode):
        """
        从嗅探器原始数据中解析 MIFARE Classic 认证数据。
        根据嗅探模式（有标签/无标签）采用不同策略。
        
        Args:
            all_data: 原始嗅探数据
            sniff_mode: 嗅探模式（PN532KillerSnifferMode.WITHOUT_TAG 或 WITH_TAG）
            
        Returns:
            list: 解析出的认证数据列表
        """
        print(f"开始使用 {sniff_mode.name} 模式解析嗅探数据...")
        auth_entries = []

        # 统一解析逻辑：两种模式都使用寻找 `0101`/`0000` 标记的方法
        hex_data = all_data.hex()
        i = 0

        while i < len(hex_data):
            # 寻找记录标记
            pos_0101 = hex_data.find('0101', i)
            pos_0000 = hex_data.find('0000', i)

            pos = -1
            if pos_0101 != -1 and pos_0000 != -1:
                pos = min(pos_0101, pos_0000)
            elif pos_0101 != -1:
                pos = pos_0101
            elif pos_0000 != -1:
                pos = pos_0000
            else:
                break

            if pos % 2 != 0:
                i = pos + 1
                continue

            # 帧结构: [标记(2)] [UID(4)] [NT(4)] [NR(4)] [AR(4)] [AT(4)] ...
            frame_start = pos + 4  # 跳过标记
            if frame_start + 44 > len(hex_data):  # 至少需要22字节(44个hex字符)来解析
                i = pos + 2
                continue

            frame_hex = hex_data[frame_start : frame_start + 44]

            try:
                uid = SnifferParser.reverse_hex(frame_hex[0:8])
                nt = SnifferParser.reverse_hex(frame_hex[8:16])
                nr = SnifferParser.reverse_hex(frame_hex[16:24])
                ar = SnifferParser.reverse_hex(frame_hex[24:32])

                if sniff_mode == PN532KillerSnifferMode.WITH_TAG:
                    at = SnifferParser.reverse_hex(frame_hex[32:40])
                    entry = {
                        'uid': uid,
                        'nt': nt,
                        'nr': nr,
                        'ar': ar,
                        'at': at
                    }
                    print(f"成功解析一个有标签的认证帧: {entry}")
                else:  # WITHOUT_TAG
                    entry = {
                        'uid': uid,
                        'nt_0': nt,
                        'nr_0': nr,
                        'ar_0': ar
                    }
                    print(f"成功解析一个无标签的认证帧: {entry}")
                
                if entry not in auth_entries:
                    auth_entries.append(entry)
                
                i = frame_start + 44
            except Exception as e:
                print(f"解析帧时出错: {e}")
                i = pos + 2

        if not auth_entries:
            print("未在数据中找到任何有效的认证信息。")

        return auth_entries
    
    @staticmethod
    def format_auth_data_for_display(auth_entries, sniff_mode: PN532KillerSnifferMode):
        """
        格式化认证数据用于显示
        
        Args:
            auth_entries: 认证数据列表
            sniff_mode: 嗅探模式
            
        Returns:
            str: 格式化后的字符串
        """
        if not auth_entries:
            return "未找到有效的认证数据"
        
        result = []
        mode_text = "有标签" if sniff_mode == PN532KillerSnifferMode.WITH_TAG else "无标签"
        result.append(f"解析成功，找到 {len(auth_entries)} 组{mode_text}认证数据:")
        
        for i, entry in enumerate(auth_entries, 1):
            result.append(f"  [{i}] {entry}")
        
        return "\n".join(result)