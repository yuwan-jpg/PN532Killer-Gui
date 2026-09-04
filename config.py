"""
配置管理模块
集中管理应用程序的配置项，避免硬编码
"""
import os
import json
from typing import Dict, Any, Optional

VERSION = "v0.6.1 Beta"

class Config:
    """配置管理类"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        # 窗口设置
        'window': {
            'title': 'PN532Killer Gui v0.6.1 Beta BY鱼丸 https://github.com/yuwan-jpg/PN532Killer-Gui',
            'min_width': 1200,
            'min_height': 700,
            'icon_path': 'pn532.ico'
        },
        
        # 通信设置
        'communication': {
            'timeout': 60,
            'read_buffer_size': 64,
            'thread_blocking_timeout': 0.1,
            'max_retries': 3
        },
        
        # 界面设置
        'ui': {
            'parameter_area_min_height': 150,
            'parameter_area_max_height': 300,
            'log_area_min_width': 200,
            'sector_display_min_width': 200,
            'splitter_initial_sizes': [300, 600],
            'splitter_stretch_factors': [1, 2]
        },
        
        # 文件路径
        'paths': {
            'history_keys_file': 'history_keys.txt',
            'key_file': 'key.txt',
            'nfc_bin_dir': 'nfc-bin',
            'temp_dir': None  # 使用系统临时目录
        },
        
        # 性能设置
        'performance': {
            'max_log_lines': 1000,  # 日志最大行数
            'buffer_flush_interval': 100,  # 缓冲区刷新间隔(ms)
            'thread_pool_size': 4,  # 线程池大小
            'memory_cleanup_interval': 300  # 内存清理间隔(秒)
        },
        
        # 调试设置
        'debug': {
            'enabled': False,
            'log_level': 'INFO',
            'log_to_file': False,
            'log_file_path': 'pn532_gui.log'
        },

        # 自动连接
        'auto_connect': {
            'enabled': False,
            'port': ''
        }
    }
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.config = self.DEFAULT_CONFIG.copy()
        self.load_config()
    
    def load_config(self) -> None:
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self._merge_config(self.config, user_config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置文件失败: {e}")
    
    def save(self) -> None:
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"保存配置文件失败: {e}")
    
    def save_config(self) -> None:
        """保存配置到文件（别名方法）"""
        self.save()
    
    def _merge_config(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """递归合并配置"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值
        key_path: 配置路径，如 'window.title' 或 'communication.timeout'
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        设置配置值
        key_path: 配置路径，如 'window.title' 或 'communication.timeout'
        """
        keys = key_path.split('.')
        config = self.config
        
        # 导航到最后一级的父级
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置值
        config[keys[-1]] = value
    
    def get_window_config(self) -> Dict[str, Any]:
        """获取窗口配置"""
        return self.config.get('window', {})
    
    def get_communication_config(self) -> Dict[str, Any]:
        """获取通信配置"""
        return self.config.get('communication', {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """获取界面配置"""
        return self.config.get('ui', {})
    
    def get_performance_config(self) -> Dict[str, Any]:
        """获取性能配置"""
        return self.config.get('performance', {})
    
    def get_debug_config(self) -> Dict[str, Any]:
        """获取调试配置"""
        return self.config.get('debug', {})

# 全局配置实例
config = Config()