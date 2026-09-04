"""
性能监控模块
监控应用程序的内存使用、CPU使用率和其他性能指标
"""
import psutil
import time
import threading
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from collections import deque

@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: float
    memory_usage_mb: float
    cpu_percent: float
    thread_count: int
    open_files: int

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_interval = 5.0  # 监控间隔(秒)
        self.callbacks: List[Callable[[PerformanceMetrics], None]] = []
        
        # 获取当前进程
        self.process = psutil.Process()
    
    def add_callback(self, callback: Callable[[PerformanceMetrics], None]) -> None:
        """添加性能指标回调函数"""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[PerformanceMetrics], None]) -> None:
        """移除性能指标回调函数"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能指标"""
        try:
            # 内存使用(MB)
            memory_info = self.process.memory_info()
            memory_usage_mb = memory_info.rss / 1024 / 1024
            
            # CPU使用率
            cpu_percent = self.process.cpu_percent()
            
            # 线程数
            thread_count = self.process.num_threads()
            
            # 打开的文件数
            try:
                open_files = len(self.process.open_files())
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                open_files = 0
            
            return PerformanceMetrics(
                timestamp=time.time(),
                memory_usage_mb=memory_usage_mb,
                cpu_percent=cpu_percent,
                thread_count=thread_count,
                open_files=open_files
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            # 进程不存在或访问被拒绝
            return PerformanceMetrics(
                timestamp=time.time(),
                memory_usage_mb=0,
                cpu_percent=0,
                thread_count=0,
                open_files=0
            )
    
    def start_monitoring(self, interval: float = 5.0) -> None:
        """开始性能监控"""
        if self.is_monitoring:
            return
        
        self.monitor_interval = interval
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self) -> None:
        """
        停止性能监控
        """
        self.is_monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=0.5)  # 减少超时时间到0.5秒
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        while self.is_monitoring:
            try:
                metrics = self.get_current_metrics()
                self.metrics_history.append(metrics)
                
                # 调用回调函数
                for callback in self.callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"性能监控回调函数执行失败: {e}")
                
                time.sleep(self.monitor_interval)
            except Exception as e:
                print(f"性能监控循环出错: {e}")
                time.sleep(1.0)
    
    def get_metrics_history(self) -> List[PerformanceMetrics]:
        """获取性能指标历史"""
        return list(self.metrics_history)
    
    def get_average_metrics(self, duration_seconds: Optional[float] = None) -> Optional[PerformanceMetrics]:
        """
        获取平均性能指标
        duration_seconds: 统计时间段(秒)，None表示所有历史数据
        """
        if not self.metrics_history:
            return None
        
        current_time = time.time()
        relevant_metrics = []
        
        for metrics in self.metrics_history:
            if duration_seconds is None or (current_time - metrics.timestamp) <= duration_seconds:
                relevant_metrics.append(metrics)
        
        if not relevant_metrics:
            return None
        
        # 计算平均值
        avg_memory = sum(m.memory_usage_mb for m in relevant_metrics) / len(relevant_metrics)
        avg_cpu = sum(m.cpu_percent for m in relevant_metrics) / len(relevant_metrics)
        avg_threads = sum(m.thread_count for m in relevant_metrics) / len(relevant_metrics)
        avg_files = sum(m.open_files for m in relevant_metrics) / len(relevant_metrics)
        
        return PerformanceMetrics(
            timestamp=current_time,
            memory_usage_mb=avg_memory,
            cpu_percent=avg_cpu,
            thread_count=int(avg_threads),
            open_files=int(avg_files)
        )
    
    def check_memory_threshold(self, threshold_mb: float) -> bool:
        """检查内存使用是否超过阈值"""
        current_metrics = self.get_current_metrics()
        return current_metrics.memory_usage_mb > threshold_mb
    
    def get_memory_trend(self, duration_seconds: float = 60.0) -> str:
        """
        获取内存使用趋势
        返回: 'increasing', 'decreasing', 'stable', 'unknown'
        """
        if len(self.metrics_history) < 2:
            return 'unknown'
        
        current_time = time.time()
        recent_metrics = [
            m for m in self.metrics_history 
            if (current_time - m.timestamp) <= duration_seconds
        ]
        
        if len(recent_metrics) < 2:
            return 'unknown'
        
        # 计算趋势
        first_half = recent_metrics[:len(recent_metrics)//2]
        second_half = recent_metrics[len(recent_metrics)//2:]
        
        avg_first = sum(m.memory_usage_mb for m in first_half) / len(first_half)
        avg_second = sum(m.memory_usage_mb for m in second_half) / len(second_half)
        
        diff_percent = (avg_second - avg_first) / avg_first * 100
        
        if diff_percent > 5:
            return 'increasing'
        elif diff_percent < -5:
            return 'decreasing'
        else:
            return 'stable'
    
    def force_garbage_collection(self) -> None:
        """强制垃圾回收"""
        import gc
        gc.collect()
    
    def get_system_info(self) -> Dict[str, any]:
        """获取系统信息"""
        try:
            return {
                'cpu_count': psutil.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / 1024 / 1024 / 1024,
                'memory_available_gb': psutil.virtual_memory().available / 1024 / 1024 / 1024,
                'disk_usage_percent': psutil.disk_usage('/').percent if hasattr(psutil, 'disk_usage') else 0
            }
        except Exception as e:
            print(f"获取系统信息失败: {e}")
            return {}

# 全局性能监控实例
performance_monitor = PerformanceMonitor()