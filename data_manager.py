import os
import time
from path_manager import PathManager


class DataManager:
    @staticmethod
    def load_default_keys():
        """加载默认密钥"""
        default_keys = {}
        for sector in range(16):  # 1K卡有16个扇区
            default_keys[sector] = {
                'key_a': 'FFFFFFFFFFFF',
                'key_b': 'FFFFFFFFFFFF'
            }
        return default_keys

    @staticmethod
    def save_keys_to_history(new_keys, card_uid=None):
        """保存密钥到历史记录"""
        try:
            history_keys_path = PathManager.get_history_keys_path()
            
            # 读取现有历史记录
            existing_keys = set()
            if os.path.exists(history_keys_path):
                with open(history_keys_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and len(line) == 12:  # 有效的密钥长度
                            existing_keys.add(line.upper())
            
            # 添加新密钥
            keys_to_add = set()
            for sector_keys in new_keys.values():
                if isinstance(sector_keys, dict):
                    for key_type, key_value in sector_keys.items():
                        if key_value and len(key_value) == 12:
                            key_upper = key_value.upper()
                            if key_upper not in existing_keys and key_upper != 'FFFFFFFFFFFF':
                                keys_to_add.add(key_upper)
            
            # 写入新密钥
            if keys_to_add:
                with open(history_keys_path, 'a', encoding='utf-8') as f:
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    if card_uid:
                        f.write(f"\n# 卡片UID: {card_uid} - {timestamp}\n")
                    else:
                        f.write(f"\n# 保存时间: {timestamp}\n")
                    
                    for key in sorted(keys_to_add):
                        f.write(f"{key}\n")
                
                return len(keys_to_add)
            
            return 0
            
        except Exception as e:
            print(f"保存密钥到历史记录失败: {str(e)}")
            return 0

    @staticmethod
    def load_history_keys():
        """加载历史密钥"""
        try:
            history_keys_path = PathManager.get_history_keys_path()
            keys = []
            
            if os.path.exists(history_keys_path):
                with open(history_keys_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and len(line) == 12:
                            keys.append(line.upper())
            
            return list(set(keys))  # 去重
            
        except Exception as e:
            print(f"加载历史密钥失败: {str(e)}")
            return []

    @staticmethod
    def validate_hex_data(data):
        """验证十六进制数据"""
        if not data:
            return False
        
        # 移除空格和其他分隔符
        clean_data = data.replace(' ', '').replace('-', '').replace(':', '')
        
        # 检查是否只包含十六进制字符
        try:
            int(clean_data, 16)
            return True
        except ValueError:
            return False

    @staticmethod
    def clean_hex_data(data):
        """清理十六进制数据"""
        if not data:
            return ""
        
        # 移除空格和其他分隔符
        clean_data = data.replace(' ', '').replace('-', '').replace(':', '').upper()
        
        # 确保是有效的十六进制
        try:
            int(clean_data, 16)
            return clean_data
        except ValueError:
            return ""

    @staticmethod
    def hex_to_ascii(hex_string):
        """
        将十六进制字符串转换为ASCII
        
        此方法现在调用独立的 SectorAnalyzer 模块。
        """
        from sector_manager import SectorAnalyzer
        return SectorAnalyzer.hex_to_ascii(hex_string)

    @staticmethod
    def is_text_data(hex_string):
        """
        判断十六进制数据是否可能是文本
        
        此方法现在调用独立的 SectorAnalyzer 模块。
        """
        from sector_manager import SectorAnalyzer
        return SectorAnalyzer.is_text_data(hex_string)

    @staticmethod
    def is_numeric_data(hex_string):
        """
        判断十六进制数据是否可能是数字
        
        此方法现在调用独立的 SectorAnalyzer 模块。
        """
        from sector_manager import SectorAnalyzer
        return SectorAnalyzer.is_numeric_data(hex_string)

    @staticmethod
    def analyze_sector_content(sector_num, block_data):
        """
        分析扇区内容
        
        此方法现在调用独立的 SectorAnalyzer 模块。
        """
        from sector_manager import SectorAnalyzer
        return SectorAnalyzer.analyze_sector_content_simple(sector_num, block_data)

    @staticmethod
    def create_temp_mfd_file(sector_data):
        """
        创建临时MFD文件
        
        此方法现在调用独立的 SectorManager 模块。
        """
        from sector_manager import SectorManager
        return SectorManager.create_temp_mfd_file(sector_data)

    @staticmethod
    def create_temp_keyfile(keys):
        """创建临时密钥文件"""
        try:
            temp_keyfile_path = PathManager.get_temp_file_path(f"temp_keys_{int(time.time() * 1000)}.txt")
            
            with open(temp_keyfile_path, 'w') as f:
                for sector_num in range(16):  # 1K卡有16个扇区
                    if sector_num in keys:
                        key_a = keys[sector_num].get('key_a', 'FFFFFFFFFFFF')
                        key_b = keys[sector_num].get('key_b', 'FFFFFFFFFFFF')
                        f.write(f"{key_a}\n{key_b}\n")
                    else:
                        f.write("FFFFFFFFFFFF\nFFFFFFFFFFFF\n")
            
            return temp_keyfile_path
        except Exception as e:
            print(f"创建临时密钥文件失败: {str(e)}")
            return None

    @staticmethod
    def cleanup_temp_files(file_paths):
        """清理临时文件"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass