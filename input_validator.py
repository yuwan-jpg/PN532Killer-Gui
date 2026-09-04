"""
输入验证工具模块
提供各种输入验证功能，确保用户输入的安全性和正确性
"""
import re
import os
from typing import Tuple, Optional


class InputValidator:
    """输入验证器类"""

    @staticmethod
    def validate_hex_string(hex_str: str, expected_length: Optional[int] = None) -> Tuple[bool, str, bytes]:
        """
        验证十六进制字符串

        Args:
            hex_str: 待验证的十六进制字符串
            expected_length: 期望的字节长度（可选）

        Returns:
            (是否有效, 错误消息, 转换后的字节数据)
        """
        if not hex_str:
            return False, "输入不能为空", b''

        # 移除空格和常见分隔符
        cleaned = hex_str.strip().replace(' ', '').replace('-', '').replace(':', '')

        # 检查是否只包含十六进制字符
        if not re.match(r'^[0-9A-Fa-f]+$', cleaned):
            return False, "输入包含非十六进制字符，请只使用0-9和A-F", b''

        # 检查长度是否为偶数
        if len(cleaned) % 2 != 0:
            return False, f"十六进制字符串长度必须为偶数，当前长度: {len(cleaned)}", b''

        # 检查期望长度
        if expected_length is not None:
            actual_bytes = len(cleaned) // 2
            if actual_bytes != expected_length:
                return False, f"数据长度错误，期望 {expected_length} 字节，实际 {actual_bytes} 字节", b''

        try:
            data_bytes = bytes.fromhex(cleaned)
            return True, "", data_bytes
        except ValueError as e:
            return False, f"十六进制转换失败: {str(e)}", b''

    @staticmethod
    def validate_mifare_key(key_str: str) -> Tuple[bool, str, bytes]:
        """
        验证 Mifare 密钥（必须是12位十六进制，6字节）

        Args:
            key_str: 密钥字符串

        Returns:
            (是否有效, 错误消息, 转换后的密钥)
        """
        return InputValidator.validate_hex_string(key_str, expected_length=6)

    @staticmethod
    def validate_uid(uid_str: str) -> Tuple[bool, str, bytes]:
        """
        验证 UID（4字节、7字节或10字节）

        Args:
            uid_str: UID字符串

        Returns:
            (是否有效, 错误消息, 转换后的UID)
        """
        if not uid_str:
            return False, "UID不能为空", b''

        cleaned = uid_str.strip().replace(' ', '').replace('-', '').replace(':', '')

        if not re.match(r'^[0-9A-Fa-f]+$', cleaned):
            return False, "UID包含非十六进制字符", b''

        byte_length = len(cleaned) // 2
        if byte_length not in [4, 7, 10]:
            return False, f"UID长度必须是4、7或10字节，当前: {byte_length}字节", b''

        try:
            uid_bytes = bytes.fromhex(cleaned)
            return True, "", uid_bytes
        except ValueError as e:
            return False, f"UID转换失败: {str(e)}", b''

    @staticmethod
    def validate_file_path(file_path: str, must_exist: bool = True,
                          allowed_extensions: Optional[list] = None) -> Tuple[bool, str]:
        """
        验证文件路径

        Args:
            file_path: 文件路径
            must_exist: 文件是否必须存在
            allowed_extensions: 允许的文件扩展名列表（如 ['.mfd', '.bin']）

        Returns:
            (是否有效, 错误消息)
        """
        if not file_path:
            return False, "文件路径不能为空"

        # 检查路径遍历攻击
        normalized_path = os.path.normpath(file_path)
        if '..' in normalized_path:
            return False, "文件路径不能包含'..'（路径遍历）"

        # 检查文件是否存在
        if must_exist and not os.path.exists(file_path):
            return False, f"文件不存在: {file_path}"

        # 检查扩展名
        if allowed_extensions:
            _, ext = os.path.splitext(file_path)
            if ext.lower() not in [e.lower() for e in allowed_extensions]:
                return False, f"不支持的文件类型，允许的类型: {', '.join(allowed_extensions)}"

        return True, ""

    @staticmethod
    def validate_integer_range(value: int, min_val: int, max_val: int,
                               field_name: str = "值") -> Tuple[bool, str]:
        """
        验证整数范围

        Args:
            value: 待验证的值
            min_val: 最小值
            max_val: 最大值
            field_name: 字段名称（用于错误消息）

        Returns:
            (是否有效, 错误消息)
        """
        if value < min_val or value > max_val:
            return False, f"{field_name}必须在 {min_val} 到 {max_val} 之间，当前值: {value}"
        return True, ""

    @staticmethod
    def validate_sector_number(sector: int, card_type: str = "1K") -> Tuple[bool, str]:
        """
        验证扇区号

        Args:
            sector: 扇区号
            card_type: 卡片类型（"1K" 或 "4K"）

        Returns:
            (是否有效, 错误消息)
        """
        max_sector = 15 if card_type == "1K" else 39
        return InputValidator.validate_integer_range(sector, 0, max_sector, "扇区号")

    @staticmethod
    def validate_block_number(block: int, sector: int, card_type: str = "1K") -> Tuple[bool, str]:
        """
        验证块号

        Args:
            block: 块号
            sector: 所属扇区号
            card_type: 卡片类型

        Returns:
            (是否有效, 错误消息)
        """
        if card_type == "1K":
            max_block = 3
        else:
            # 4K卡：扇区0-31每扇区4块，扇区32-39每扇区16块
            max_block = 3 if sector < 32 else 15

        return InputValidator.validate_integer_range(block, 0, max_block, "块号")

    @staticmethod
    def sanitize_command_input(cmd_str: str) -> Tuple[bool, str, str]:
        """
        清理和验证命令输入，防止命令注入

        Args:
            cmd_str: 命令字符串

        Returns:
            (是否有效, 错误消息, 清理后的命令)
        """
        if not cmd_str:
            return False, "命令不能为空", ""

        # 移除危险字符
        dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r', '\\']
        for char in dangerous_chars:
            if char in cmd_str:
                return False, f"命令包含非法字符: {char}", ""

        # 清理空白字符
        cleaned = cmd_str.strip()

        return True, "", cleaned

    @staticmethod
    def validate_port_name(port: str) -> Tuple[bool, str]:
        """
        验证串口名称

        Args:
            port: 串口名称

        Returns:
            (是否有效, 错误消息)
        """
        if not port:
            return False, "串口名称不能为空"

        # Windows: COM1-COM256
        # Linux/Mac: /dev/ttyUSB*, /dev/ttyACM*, /dev/cu.*
        import platform
        system = platform.system()

        if system == "Windows":
            if not re.match(r'^COM\d+$', port, re.IGNORECASE):
                return False, "Windows串口格式应为 COMx（如 COM3）"
        else:
            if not re.match(r'^/dev/(tty(USB|ACM|S)|cu\.)', port):
                return False, "串口格式应为 /dev/ttyUSBx 或 /dev/ttyACMx"

        return True, ""


class SecureKeyStorage:
    """安全密钥存储（简单加密）"""

    @staticmethod
    def xor_encrypt_decrypt(data: bytes, key: bytes) -> bytes:
        """
        简单的XOR加密/解密
        注意：这只是基础保护，不是强加密

        Args:
            data: 数据
            key: 密钥

        Returns:
            加密/解密后的数据
        """
        key_len = len(key)
        return bytes([data[i] ^ key[i % key_len] for i in range(len(data))])

    @staticmethod
    def obfuscate_key(key_hex: str) -> str:
        """
        混淆密钥用于存储

        Args:
            key_hex: 十六进制密钥字符串

        Returns:
            混淆后的字符串
        """
        try:
            key_bytes = bytes.fromhex(key_hex)
            # 使用固定密钥进行XOR（实际应用中应使用更安全的方法）
            xor_key = b'PN532SecureKey!!'
            encrypted = SecureKeyStorage.xor_encrypt_decrypt(key_bytes, xor_key)
            return encrypted.hex().upper()
        except:
            return key_hex

    @staticmethod
    def deobfuscate_key(obfuscated_hex: str) -> str:
        """
        解混淆密钥

        Args:
            obfuscated_hex: 混淆后的十六进制字符串

        Returns:
            原始密钥字符串
        """
        try:
            encrypted_bytes = bytes.fromhex(obfuscated_hex)
            xor_key = b'PN532SecureKey!!'
            decrypted = SecureKeyStorage.xor_encrypt_decrypt(encrypted_bytes, xor_key)
            return decrypted.hex().upper()
        except:
            return obfuscated_hex
