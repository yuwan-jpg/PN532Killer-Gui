"""
统一错误处理和异常管理系统
提供标准化的错误处理、异常捕获和用户友好的错误消息
"""
import sys
import traceback
import functools
from typing import Optional, Callable, Any, Dict, Type, Union
from enum import Enum
from PyQt6.QtWidgets import QMessageBox, QWidget
from PyQt6.QtCore import QObject, pyqtSignal
import logging

class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 轻微错误，不影响主要功能
    MEDIUM = "medium"     # 中等错误，影响部分功能
    HIGH = "high"         # 严重错误，影响主要功能
    CRITICAL = "critical" # 致命错误，应用程序无法继续运行

class ErrorCategory(Enum):
    """错误类别"""
    COMMUNICATION = "communication"  # 通信错误
    FILE_IO = "file_io"             # 文件IO错误
    VALIDATION = "validation"        # 数据验证错误
    HARDWARE = "hardware"           # 硬件错误
    NETWORK = "network"             # 网络错误
    UI = "ui"                       # 界面错误
    SYSTEM = "system"               # 系统错误
    UNKNOWN = "unknown"             # 未知错误

class AppError(Exception):
    """应用程序自定义异常基类"""
    
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM, 
                 error_code: Optional[str] = None, 
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = None
        
        # 自动设置时间戳
        import time
        self.timestamp = time.time()

class CommunicationError(AppError):
    """通信错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.COMMUNICATION, **kwargs)

class FileIOError(AppError):
    """文件IO错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.FILE_IO, **kwargs)

class ValidationError(AppError):
    """数据验证错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.VALIDATION, **kwargs)

class HardwareError(AppError):
    """硬件错误"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.HARDWARE, **kwargs)

class ErrorHandler(QObject):
    """错误处理器"""
    
    # 错误信号
    error_occurred = pyqtSignal(AppError)
    critical_error_occurred = pyqtSignal(AppError)
    
    def __init__(self, parent_widget: Optional[QWidget] = None):
        super().__init__()
        self.parent_widget = parent_widget
        self.logger = logging.getLogger("ErrorHandler")
        
        # 错误统计
        self.error_counts: Dict[ErrorCategory, int] = {cat: 0 for cat in ErrorCategory}
        self.recent_errors: list = []
        self.max_recent_errors = 50
        
        # 错误消息映射
        self.error_messages = {
            ErrorCategory.COMMUNICATION: {
                "connection_failed": "无法连接到设备，请检查连接",
                "timeout": "操作超时，请重试",
                "invalid_response": "设备响应无效"
            },
            ErrorCategory.FILE_IO: {
                "file_not_found": "文件未找到",
                "permission_denied": "文件访问权限不足",
                "invalid_format": "文件格式无效"
            },
            ErrorCategory.VALIDATION: {
                "invalid_input": "输入数据无效",
                "missing_required": "缺少必需的参数",
                "out_of_range": "数值超出有效范围"
            },
            ErrorCategory.HARDWARE: {
                "device_not_found": "未找到设备",
                "device_busy": "设备正忙",
                "hardware_failure": "硬件故障"
            }
        }
    
    def handle_exception(self, exc_type: Type[Exception], exc_value: Exception, 
                        exc_traceback: Any, show_dialog: bool = True) -> None:
        """处理异常"""
        # 创建错误对象
        if isinstance(exc_value, AppError):
            error = exc_value
        else:
            # 将标准异常转换为AppError
            error = self._convert_standard_exception(exc_value)
        
        # 记录错误
        self._log_error(error, exc_traceback)
        
        # 更新统计
        self._update_error_stats(error)
        
        # 发送信号
        if error.severity == ErrorSeverity.CRITICAL:
            self.critical_error_occurred.emit(error)
        else:
            self.error_occurred.emit(error)
        
        # 显示用户对话框
        if show_dialog:
            self._show_error_dialog(error)
    
    def _convert_standard_exception(self, exception: Exception) -> AppError:
        """将标准异常转换为AppError"""
        exc_type = type(exception)
        message = str(exception)
        
        # 根据异常类型确定类别和严重程度
        if issubclass(exc_type, (ConnectionError, TimeoutError)):
            return CommunicationError(message, severity=ErrorSeverity.HIGH)
        elif issubclass(exc_type, (FileNotFoundError, PermissionError, IOError)):
            return FileIOError(message, severity=ErrorSeverity.MEDIUM)
        elif issubclass(exc_type, (ValueError, TypeError)):
            return ValidationError(message, severity=ErrorSeverity.LOW)
        elif issubclass(exc_type, MemoryError):
            return AppError(message, ErrorCategory.SYSTEM, ErrorSeverity.CRITICAL)
        else:
            return AppError(message, ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM)
    
    def _log_error(self, error: AppError, traceback_obj: Any = None) -> None:
        """记录错误到日志"""
        log_message = f"[{error.category.value.upper()}] {error.message}"
        
        if error.error_code:
            log_message += f" (代码: {error.error_code})"
        
        if error.details:
            log_message += f" 详情: {error.details}"
        
        # 根据严重程度选择日志级别
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=traceback_obj)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, exc_info=traceback_obj)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _update_error_stats(self, error: AppError) -> None:
        """更新错误统计"""
        self.error_counts[error.category] += 1
        
        # 添加到最近错误列表
        self.recent_errors.append({
            'timestamp': error.timestamp,
            'category': error.category,
            'severity': error.severity,
            'message': error.message,
            'error_code': error.error_code
        })
        
        # 限制最近错误列表大小
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors = self.recent_errors[-self.max_recent_errors:]
    
    def _show_error_dialog(self, error: AppError) -> None:
        """显示错误对话框"""
        if not self.parent_widget:
            return
        
        # 获取用户友好的错误消息
        user_message = self._get_user_friendly_message(error)
        
        # 根据严重程度选择对话框类型
        if error.severity == ErrorSeverity.CRITICAL:
            icon = QMessageBox.Icon.Critical
            title = "严重错误"
        elif error.severity == ErrorSeverity.HIGH:
            icon = QMessageBox.Icon.Critical
            title = "错误"
        elif error.severity == ErrorSeverity.MEDIUM:
            icon = QMessageBox.Icon.Warning
            title = "警告"
        else:
            icon = QMessageBox.Icon.Information
            title = "提示"
        
        # 创建消息框
        msg_box = QMessageBox(self.parent_widget)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(user_message)
        
        # 添加详细信息
        if error.details or error.error_code:
            details = []
            if error.error_code:
                details.append(f"错误代码: {error.error_code}")
            if error.details:
                for key, value in error.details.items():
                    details.append(f"{key}: {value}")
            msg_box.setDetailedText("\n".join(details))
        
        msg_box.exec()
    
    def _get_user_friendly_message(self, error: AppError) -> str:
        """获取用户友好的错误消息"""
        category_messages = self.error_messages.get(error.category, {})
        
        if error.error_code and error.error_code in category_messages:
            return category_messages[error.error_code]
        
        # 尝试根据消息内容匹配
        message_lower = error.message.lower()
        for code, friendly_msg in category_messages.items():
            if code in message_lower:
                return friendly_msg
        
        # 返回原始消息
        return error.message
    
    def get_error_stats(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            'total_errors': sum(self.error_counts.values()),
            'by_category': dict(self.error_counts),
            'recent_errors_count': len(self.recent_errors),
            'recent_errors': self.recent_errors[-10:]  # 最近10个错误
        }
    
    def clear_error_stats(self) -> None:
        """清除错误统计"""
        self.error_counts = {cat: 0 for cat in ErrorCategory}
        self.recent_errors.clear()

def error_handler(category: ErrorCategory = ErrorCategory.UNKNOWN, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 error_code: Optional[str] = None,
                 show_dialog: bool = True,
                 reraise: bool = False):
    """错误处理装饰器"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AppError:
                # 已经是AppError，直接重新抛出
                if reraise:
                    raise
            except Exception as e:
                # 转换为AppError
                app_error = AppError(
                    message=str(e),
                    category=category,
                    severity=severity,
                    error_code=error_code
                )
                
                if reraise:
                    raise app_error
                else:
                    # 这里可以添加全局错误处理器的调用
                    logging.getLogger().error(f"装饰器捕获异常: {app_error.message}", exc_info=True)
                    return None
        
        return wrapper
    return decorator

def safe_execute(func: Callable, *args, default_return: Any = None, 
                error_handler_instance: Optional[ErrorHandler] = None, **kwargs) -> Any:
    """安全执行函数"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if error_handler_instance:
            error_handler_instance.handle_exception(type(e), e, sys.exc_info()[2])
        else:
            logging.getLogger().error(f"安全执行失败: {e}", exc_info=True)
        return default_return

# 全局错误处理器实例
global_error_handler: Optional[ErrorHandler] = None

def set_global_error_handler(handler: ErrorHandler) -> None:
    """设置全局错误处理器"""
    global global_error_handler
    global_error_handler = handler

def get_global_error_handler() -> Optional[ErrorHandler]:
    """获取全局错误处理器"""
    return global_error_handler