"""
改进的日志系统
支持多级别日志、控制台输出和格式化
注意：已移除本地文件保存功能，仅输出到控制台
"""
import logging
import os
import sys
import threading
from typing import Optional, Dict, Any
from enum import Enum

class LogLevel(Enum):
    """日志级别枚举"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

class LogFormatter(logging.Formatter):
    """自定义日志格式化器"""
    
    def __init__(self, include_thread: bool = True):
        self.include_thread = include_thread
        
        # 不同级别的颜色代码(用于控制台输出)
        self.colors = {
            'DEBUG': '\033[36m',      # 青色
            'INFO': '\033[32m',       # 绿色
            'WARNING': '\033[33m',    # 黄色
            'ERROR': '\033[31m',      # 红色
            'CRITICAL': '\033[35m',   # 紫色
            'RESET': '\033[0m'        # 重置
        }
        
        # 基础格式
        base_format = '%(asctime)s - %(name)s - %(levelname)s'
        if include_thread:
            base_format += ' - [%(thread)d:%(threadName)s]'
        base_format += ' - %(message)s'
        
        super().__init__(base_format, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record):
        """格式化日志记录"""
        # 添加颜色(仅用于控制台)
        if hasattr(record, 'use_color') and record.use_color:
            levelname = record.levelname
            if levelname in self.colors:
                record.levelname = f"{self.colors[levelname]}{levelname}{self.colors['RESET']}"
        
        return super().format(record)

class Logger:
    """改进的日志器"""
    
    def __init__(self, name: str = "PN532GUI"):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # 防止重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
        
        self.lock = threading.Lock()
    
    def _setup_handlers(self) -> None:
        """设置日志处理器 - 仅控制台输出，不保存到文件"""

        class ColoredHandler(logging.StreamHandler):
            def emit(self, record):
                record.use_color = True
                super().emit(record)

        console_handler = ColoredHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = LogFormatter(include_thread=True)
        console_handler.setFormatter(console_formatter)

        self.logger.addHandler(console_handler)
    
    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """调试日志"""
        self._log(LogLevel.DEBUG, message, extra_data)
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """信息日志"""
        self._log(LogLevel.INFO, message, extra_data)
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """警告日志"""
        self._log(LogLevel.WARNING, message, extra_data)
    
    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """错误日志"""
        self._log(LogLevel.ERROR, message, extra_data, exc_info)
    
    def critical(self, message: str, extra_data: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """严重错误日志"""
        self._log(LogLevel.CRITICAL, message, extra_data, exc_info)
    
    def _log(self, level: LogLevel, message: str, extra_data: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        """内部日志方法"""
        with self.lock:
            extra = {'extra_data': extra_data} if extra_data else {}
            self.logger.log(level.value, message, exc_info=exc_info, extra=extra)
    
    def set_level(self, level: LogLevel) -> None:
        """设置日志级别"""
        self.logger.setLevel(level.value)

        # 更新所有处理器的级别
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                # 控制台处理器
                handler.setLevel(level.value)
    
    def log_performance(self, operation: str, duration: float, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """记录性能日志"""
        perf_data = {'operation': operation, 'duration_ms': duration * 1000}
        if extra_data:
            perf_data.update(extra_data)
        
        if duration > 1.0:  # 超过1秒的操作记录为警告
            self.warning(f"慢操作: {operation} 耗时 {duration:.3f}秒", perf_data)
        else:
            self.debug(f"操作完成: {operation} 耗时 {duration:.3f}秒", perf_data)
    
    def log_memory_usage(self, operation: str, memory_mb: float) -> None:
        """记录内存使用日志"""
        memory_data = {'operation': operation, 'memory_mb': memory_mb}
        
        if memory_mb > 100:  # 超过100MB记录为警告
            self.warning(f"高内存使用: {operation} 使用 {memory_mb:.1f}MB", memory_data)
        else:
            self.debug(f"内存使用: {operation} 使用 {memory_mb:.1f}MB", memory_data)
    
    def log_exception(self, message: str, exception: Exception, extra_data: Optional[Dict[str, Any]] = None) -> None:
        """记录异常日志"""
        exc_data = {
            'exception_type': type(exception).__name__,
            'exception_message': str(exception)
        }
        if extra_data:
            exc_data.update(extra_data)
        
        self.error(f"{message}: {exception}", exc_data, exc_info=True)
    
    def create_child_logger(self, child_name: str) -> 'Logger':
        """创建子日志器"""
        full_name = f"{self.name}.{child_name}"
        return Logger(full_name)

class PerformanceLogger:
    """性能日志记录器"""
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.start_time: Optional[float] = None
        self.operation_name: str = ""
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            self.logger.log_performance(self.operation_name, duration)
    
    def start(self, operation_name: str) -> None:
        """开始性能记录"""
        import time
        self.operation_name = operation_name
        self.start_time = time.time()
        self.logger.debug(f"开始操作: {operation_name}")
    
    def end(self, extra_data: Optional[Dict[str, Any]] = None) -> float:
        """结束性能记录"""
        if self.start_time is None:
            return 0.0
        
        import time
        duration = time.time() - self.start_time
        self.logger.log_performance(self.operation_name, duration, extra_data)
        self.start_time = None
        return duration

# 全局日志器实例
app_logger = Logger("PN532GUI")
comm_logger = Logger("PN532GUI.Communication")
ui_logger = Logger("PN532GUI.UI")
perf_logger = PerformanceLogger(app_logger)