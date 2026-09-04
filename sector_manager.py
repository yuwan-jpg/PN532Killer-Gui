"""
扇区管理模块
用于处理 MIFARE Classic 扇区的分析、解析和管理功能
"""

import time
from typing import List, Dict, Any
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from path_manager import PathManager


class SectorAnalyzer:
    """扇区分析器"""
    
    @staticmethod
    def hex_to_ascii(hex_string: str) -> str:
        """将十六进制字符串转换为ASCII字符"""
        try:
            ascii_chars = []
            for i in range(0, len(hex_string), 2):
                hex_byte = hex_string[i:i+2]
                byte_val = int(hex_byte, 16)
                if 32 <= byte_val <= 126:
                    ascii_chars.append(chr(byte_val))
                else:
                    ascii_chars.append('.')
            return ''.join(ascii_chars)
        except:
            return ""
    
    @staticmethod
    def is_text_data(hex_string: str) -> bool:
        """判断十六进制数据是否为文本数据"""
        try:
            text_chars = 0
            total_chars = len(hex_string) // 2
            for i in range(0, len(hex_string), 2):
                hex_byte = hex_string[i:i+2]
                byte_val = int(hex_byte, 16)
                if 32 <= byte_val <= 126:
                    text_chars += 1
            return text_chars / total_chars > 0.5
        except:
            return False
    
    @staticmethod
    def is_numeric_data(hex_string: str) -> bool:
        """判断十六进制数据是否为数值数据"""
        try:
            for i in range(0, len(hex_string), 8):
                chunk = hex_string[i:i+8]
                if len(chunk) == 8:
                    val = int(chunk, 16)
                    if 0 < val < 1000000:
                        return True
            return False
        except:
            return False
    
    @staticmethod
    def analyze_sector_content(sector_num: int, block_data: List[str]) -> Dict[str, Any]:
        """
        分析扇区内容
        
        Args:
            sector_num: 扇区编号
            block_data: 块数据列表
            
        Returns:
            dict: 分析结果
        """
        analysis = {
            "sector_num": sector_num,
            "block_count": len(block_data),
            "data_blocks": [],
            "trailer_block": None,
            "possible_formats": []
        }
        
        for i, hex_data in enumerate(block_data):
            block_info = {
                "block_num": i,
                "hex_data": hex_data,
                "ascii_data": SectorAnalyzer.hex_to_ascii(hex_data),
                "analysis": []
            }
            
            if i == len(block_data) - 1:
                # 尾块
                analysis["trailer_block"] = block_info
                block_info["analysis"].append("尾块 - 包含访问控制位和密钥")
            else:
                # 数据块
                analysis["data_blocks"].append(block_info)
                if hex_data == "00" * 16:
                    block_info["analysis"].append("空块")
                elif SectorAnalyzer.is_text_data(hex_data):
                    block_info["analysis"].append("可能包含文本数据")
                elif SectorAnalyzer.is_numeric_data(hex_data):
                    block_info["analysis"].append("可能包含数值数据")
                else:
                    block_info["analysis"].append("二进制数据")
        
        # 分析扇区格式
        if sector_num == 0:
            analysis["possible_formats"].append("制造商块 - 包含UID和制造商数据")
        elif all(block["hex_data"] == "00" * 16 for block in analysis["data_blocks"]):
            analysis["possible_formats"].append("空扇区")
        elif any("文本" in str(block.get("analysis", [])) for block in analysis["data_blocks"]):
            analysis["possible_formats"].append("可能包含文本信息")
        
        return analysis
    
    @staticmethod
    def analyze_sector_content_simple(sector_num: int, block_data: List[str]) -> Dict[str, Any]:
        """
        简化版扇区内容分析（兼容data_manager的格式）
        
        Args:
            sector_num: 扇区编号
            block_data: 块数据列表
            
        Returns:
            dict: 分析结果
        """
        analysis = {
            'sector': sector_num,
            'blocks': [],
            'summary': {
                'has_text': False,
                'has_numbers': False,
                'is_empty': True,
                'access_bits': None
            }
        }
        
        for block_num, block_hex in enumerate(block_data):
            block_analysis = {
                'block': block_num,
                'hex': block_hex,
                'ascii': SectorAnalyzer.hex_to_ascii(block_hex),
                'is_text': SectorAnalyzer.is_text_data(block_hex),
                'is_numeric': SectorAnalyzer.is_numeric_data(block_hex),
                'is_empty': block_hex.replace(' ', '').replace('0', '') == ''
            }
            
            analysis['blocks'].append(block_analysis)
            
            # 更新摘要
            if not block_analysis['is_empty']:
                analysis['summary']['is_empty'] = False
            if block_analysis['is_text']:
                analysis['summary']['has_text'] = True
            if block_analysis['is_numeric']:
                analysis['summary']['has_numbers'] = True
        
        return analysis


class SectorManager:
    """扇区管理器"""
    
    @staticmethod
    def create_temp_mfd_file(sector_data: Dict[int, List[str]]) -> str:
        """
        创建临时MFD文件
        
        Args:
            sector_data: 扇区数据字典 {扇区号: [块数据列表]}
            
        Returns:
            str: 临时文件路径
        """
        try:
            temp_mfd_path = PathManager.get_temp_file_path(f"temp_write_{int(time.time() * 1000)}.mfd")
            
            # 创建1K卡片的空白数据
            mfd_content = bytearray(1024)
            
            # 填充扇区数据
            for sector_num, data in sector_data.items():
                if sector_num >= 16:  # 1K卡只有16个扇区
                    continue
                
                sector_start = sector_num * 64
                for block_num, block_hex in enumerate(data):
                    if block_num >= 4:  # 每个扇区最多4个块
                        break
                    
                    block_start = sector_start + block_num * 16
                    block_bytes = bytes.fromhex(block_hex.replace(' ', ''))
                    
                    # 确保块数据长度为16字节
                    if len(block_bytes) > 16:
                        block_bytes = block_bytes[:16]
                    elif len(block_bytes) < 16:
                        block_bytes += b'\x00' * (16 - len(block_bytes))
                    
                    mfd_content[block_start:block_start + 16] = block_bytes
            
            # 写入文件
            with open(temp_mfd_path, 'wb') as f:
                f.write(mfd_content)
            
            return temp_mfd_path
        except Exception as e:
            print(f"创建临时MFD文件失败: {e}")
            return None
    
    @staticmethod
    def extract_keys_from_sectors(sectors_data: List[Dict]) -> Dict[int, Dict[str, str]]:
        """
        从扇区数据中提取密钥
        
        Args:
            sectors_data: 扇区数据列表
            
        Returns:
            dict: 密钥字典 {扇区号: {'key_a': 'xxx', 'key_b': 'xxx'}}
        """
        keys = {}
        
        for sector_num in range(16):  # 1K卡有16个扇区
            if sector_num in sectors_data:
                key_a = sectors_data[sector_num].get('key_a', 'FFFFFFFFFFFF')
                key_b = sectors_data[sector_num].get('key_b', 'FFFFFFFFFFFF')
            else:
                key_a = 'FFFFFFFFFFFF'
                key_b = 'FFFFFFFFFFFF'
            
            keys[sector_num] = {
                'key_a': key_a,
                'key_b': key_b
            }
        
        return keys
    
    @staticmethod
    def format_sector_report(sector_num: int, analysis: Dict[str, Any]) -> str:
        """
        格式化扇区分析报告
        
        Args:
            sector_num: 扇区编号
            analysis: 分析结果
            
        Returns:
            str: 格式化的报告
        """
        report = f"扇区 {sector_num} 数据分析报告\n"
        report += "=" * 50 + "\n\n"
        report += f"扇区编号: {analysis['sector_num']}\n"
        report += f"块数量: {analysis['block_count']}\n"
        
        if analysis.get('possible_formats'):
            report += f"可能格式: {', '.join(analysis['possible_formats'])}\n"
        
        report += "\n数据块分析:\n"
        report += "-" * 30 + "\n"
        
        for block in analysis.get('data_blocks', []):
            report += f"块 {block['block_num']}: {block['hex_data']}\n"
            report += f"  ASCII: {block['ascii_data']}\n"
            report += f"  分析: {', '.join(block['analysis'])}\n\n"
        
        if analysis.get('trailer_block'):
            trailer = analysis['trailer_block']
            report += f"尾块: {trailer['hex_data']}\n"
            report += f"  分析: {', '.join(trailer['analysis'])}\n"
        
        return report


class SectorAnalysisDialog(QDialog):
    """扇区分析对话框"""
    
    def __init__(self, parent, sector_num: int, analysis: Dict[str, Any]):
        super().__init__(parent)
        self.sector_num = sector_num
        self.analysis = analysis
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle(f"扇区 {self.sector_num} 数据解析")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # 文本显示区域
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Consolas", 10))
        
        # 生成报告
        report = SectorManager.format_sector_report(self.sector_num, self.analysis)
        self.text_area.setPlainText(report)
        
        layout.addWidget(self.text_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("复制报告")
        copy_btn.clicked.connect(self.copy_report)
        button_layout.addWidget(copy_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def copy_report(self):
        """复制报告到剪贴板"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text_area.toPlainText())