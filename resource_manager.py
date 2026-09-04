"""
资源管理器
管理线程池、内存使用和其他系统资源
"""
import threading
import queue
import time
import gc
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Dict, List, Optional, Callable, Any
from contextlib import contextmanager
import weakref

class ResourceManager:
    """资源管理器"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_pool: Optional[ThreadPoolExecutor] = None
        self.active_threads: Dict[str, threading.Thread] = {}
        self.thread_lock = threading.Lock()
        
        # 内存管理
        self.memory_threshold_mb = 500  # 内存阈值(MB)
        self.gc_interval = 30  # 垃圾回收间隔(秒)
        self.last_gc_time = time.time()
        
        # 资源追踪
        self.resource_refs: List[weakref.ref] = []
        self.cleanup_callbacks: List[Callable[[], None]] = []
        
        # 初始化线程池
        self._init_thread_pool()
    
    def _init_thread_pool(self) -> None:
        """初始化线程池"""
        if self.thread_pool is None:
            self.thread_pool = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="ResourceManager"
            )
    
    def submit_task(self, func: Callable, *args, **kwargs) -> Future:
        """提交任务到线程池"""
        if self.thread_pool is None:
            self._init_thread_pool()
        
        return self.thread_pool.submit(func, *args, **kwargs)
    
    def register_thread(self, thread_id: str, thread: threading.Thread) -> None:
        """注册线程"""
        with self.thread_lock:
            self.active_threads[thread_id] = thread
    
    def unregister_thread(self, thread_id: str) -> None:
        """注销线程"""
        with self.thread_lock:
            if thread_id in self.active_threads:
                del self.active_threads[thread_id]
    
    def get_active_thread_count(self) -> int:
        """获取活跃线程数"""
        with self.thread_lock:
            # 清理已结束的线程
            finished_threads = [
                tid for tid, thread in self.active_threads.items()
                if not thread.is_alive()
            ]
            for tid in finished_threads:
                del self.active_threads[tid]
            
            return len(self.active_threads)
    
    def stop_all_threads(self, timeout: float = 5.0) -> None:
        """停止所有线程"""
        with self.thread_lock:
            threads_to_stop = list(self.active_threads.values())
        
        if not threads_to_stop:
            return
        
        # 等待线程结束
        per_thread_timeout = timeout / len(threads_to_stop)
        for thread in threads_to_stop:
            if thread.is_alive():
                thread.join(timeout=per_thread_timeout)
        
        # 清理线程池
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True, timeout=timeout)
            self.thread_pool = None
    
    def register_resource(self, resource: Any) -> None:
        """注册资源用于追踪"""
        self.resource_refs.append(weakref.ref(resource))
    
    def add_cleanup_callback(self, callback: Callable[[], None]) -> None:
        """添加清理回调函数"""
        self.cleanup_callbacks.append(callback)
    
    def cleanup_resources(self) -> None:
        """清理资源"""
        # 执行清理回调
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except Exception as e:
                print(f"资源清理回调执行失败: {e}")
        
        # 清理弱引用
        self.resource_refs = [ref for ref in self.resource_refs if ref() is not None]
        
        # 强制垃圾回收
        self.force_garbage_collection()
    
    def force_garbage_collection(self) -> None:
        """强制垃圾回收"""
        gc.collect()
        self.last_gc_time = time.time()
    
    def check_memory_and_gc(self) -> None:
        """检查内存使用并执行垃圾回收"""
        current_time = time.time()
        
        # 定期垃圾回收
        if current_time - self.last_gc_time > self.gc_interval:
            self.force_garbage_collection()
        
        # 检查内存使用
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            
            if memory_mb > self.memory_threshold_mb:
                print(f"内存使用过高: {memory_mb:.1f}MB, 执行清理...")
                self.cleanup_resources()
        except ImportError:
            # psutil不可用，跳过内存检查
            pass
        except Exception as e:
            print(f"内存检查失败: {e}")
    
    def get_resource_stats(self) -> Dict[str, Any]:
        """获取资源统计信息"""
        stats = {
            'active_threads': self.get_active_thread_count(),
            'thread_pool_active': self.thread_pool is not None,
            'registered_resources': len([ref for ref in self.resource_refs if ref() is not None]),
            'cleanup_callbacks': len(self.cleanup_callbacks)
        }
        
        # 添加内存信息
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            stats.update({
                'memory_rss_mb': memory_info.rss / 1024 / 1024,
                'memory_vms_mb': memory_info.vms / 1024 / 1024
            })
        except (ImportError, Exception):
            pass
        
        return stats
    
    def shutdown(self) -> None:
        """关闭资源管理器"""
        print("正在关闭资源管理器...")
        
        # 停止所有线程
        self.stop_all_threads()
        
        # 清理资源
        self.cleanup_resources()
        
        # 清空回调
        self.cleanup_callbacks.clear()
        
        print("资源管理器已关闭")

@contextmanager
def managed_thread(resource_manager: ResourceManager, thread_id: str):
    """线程管理上下文管理器"""
    thread = threading.current_thread()
    resource_manager.register_thread(thread_id, thread)
    try:
        yield thread
    finally:
        resource_manager.unregister_thread(thread_id)

class ThreadSafeQueue:
    """线程安全队列包装器"""
    
    def __init__(self, maxsize: int = 0):
        self.queue = queue.Queue(maxsize=maxsize)
        self.resource_manager: Optional[ResourceManager] = None
    
    def set_resource_manager(self, resource_manager: ResourceManager) -> None:
        """设置资源管理器"""
        self.resource_manager = resource_manager
        resource_manager.register_resource(self)
    
    def put(self, item: Any, block: bool = True, timeout: Optional[float] = None) -> None:
        """放入项目"""
        self.queue.put(item, block=block, timeout=timeout)
    
    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """获取项目"""
        return self.queue.get(block=block, timeout=timeout)
    
    def empty(self) -> bool:
        """检查队列是否为空"""
        return self.queue.empty()
    
    def qsize(self) -> int:
        """获取队列大小"""
        return self.queue.qsize()
    
    def clear(self) -> None:
        """清空队列"""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

class MemoryPool:
    """内存池管理器"""
    
    def __init__(self, initial_size: int = 10):
        self.pool: List[bytearray] = []
        self.pool_lock = threading.Lock()
        self.initial_size = initial_size
        self.buffer_size = 1024  # 默认缓冲区大小
        
        # 预分配缓冲区
        self._preallocate_buffers()
    
    def _preallocate_buffers(self) -> None:
        """预分配缓冲区"""
        with self.pool_lock:
            for _ in range(self.initial_size):
                self.pool.append(bytearray(self.buffer_size))
    
    def get_buffer(self, size: Optional[int] = None) -> bytearray:
        """获取缓冲区"""
        if size is None:
            size = self.buffer_size
        
        with self.pool_lock:
            if self.pool and len(self.pool[-1]) >= size:
                buffer = self.pool.pop()
                # 重置缓冲区
                buffer[:] = b'\x00' * len(buffer)
                return buffer
        
        # 创建新缓冲区
        return bytearray(size)
    
    def return_buffer(self, buffer: bytearray) -> None:
        """归还缓冲区"""
        with self.pool_lock:
            if len(self.pool) < self.initial_size * 2:  # 限制池大小
                self.pool.append(buffer)
    
    def clear_pool(self) -> None:
        """清空内存池"""
        with self.pool_lock:
            self.pool.clear()

# 全局资源管理器实例
resource_manager = ResourceManager()
memory_pool = MemoryPool()