import asyncio
from typing import Any, List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging
from functools import wraps
import time

logger = logging.getLogger(__name__)

class AsyncTaskQueue:
    """Async task queue with concurrency control"""
    
    def __init__(self, max_concurrent: int = 10):
        self.queue = asyncio.Queue()
        self.max_concurrent = max_concurrent
        self.running_tasks = set()
        self.results = {}
    
    async def add_task(self, task_id: str, coro):
        """Add task to queue"""
        await self.queue.put((task_id, coro))
    
    async def process_tasks(self):
        """Process tasks with concurrency limit"""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def worker():
            while True:
                try:
                    task_id, coro = await self.queue.get()
                    
                    async with semaphore:
                        self.running_tasks.add(task_id)
                        try:
                            result = await coro
                            self.results[task_id] = {"status": "success", "result": result}
                        except Exception as e:
                            logger.error(f"Task {task_id} failed: {e}")
                            self.results[task_id] = {"status": "error", "error": str(e)}
                        finally:
                            self.running_tasks.discard(task_id)
                    
                    self.queue.task_done()
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Worker error: {e}")
        
        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(self.max_concurrent)]
        
        # Wait for all tasks
        await self.queue.join()
        
        # Cancel workers
        for w in workers:
            w.cancel()
    
    def get_result(self, task_id: str) -> Optional[Dict]:
        """Get task result"""
        return self.results.get(task_id)
    
    def is_running(self, task_id: str) -> bool:
        """Check if task is running"""
        return task_id in self.running_tasks

class ThreadPoolManager:
    """Manage thread pool for CPU-bound tasks"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.futures = {}
    
    async def run_in_thread(self, func: Callable, *args, **kwargs) -> Any:
        """Run function in thread pool"""
        loop = asyncio.get_event_loop()
        
        future = loop.run_in_executor(
            self.executor,
            func,
            *args
        )
        
        return await future
    
    def submit(self, task_id: str, func: Callable, *args, **kwargs):
        """Submit task to thread pool"""
        future = self.executor.submit(func, *args, **kwargs)
        self.futures[task_id] = future
        return future
    
    def get_result(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Get task result"""
        if task_id in self.futures:
            return self.futures[task_id].result(timeout=timeout)
        return None
    
    def shutdown(self, wait: bool = True):
        """Shutdown thread pool"""
        self.executor.shutdown(wait=wait)

# Global thread pool
thread_pool = ThreadPoolManager()

def async_timeout(seconds: float):
    """Decorator to add timeout to async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {seconds} seconds")
                raise
        return wrapper
    return decorator

class RateLimiter:
    """Async rate limiter"""
    
    def __init__(self, rate: int, per: float):
        self.rate = rate
        self.per = per
        self.allowance = rate
        self.last_check = time.time()
    
    async def acquire(self):
        """Acquire permission to proceed"""
        current = time.time()
        time_passed = current - self.last_check
        self.last_check = current
        
        self.allowance += time_passed * (self.rate / self.per)
        
        if self.allowance > self.rate:
            self.allowance = self.rate
        
        if self.allowance < 1.0:
            sleep_time = (1.0 - self.allowance) * (self.per / self.rate)
            await asyncio.sleep(sleep_time)
            self.allowance = 0.0
        else:
            self.allowance -= 1.0

async def run_parallel_tasks(tasks: List[Callable], max_concurrent: int = 5) -> List[Any]:
    """Run tasks in parallel with concurrency limit"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def run_with_semaphore(task):
        async with semaphore:
            if asyncio.iscoroutinefunction(task):
                return await task()
            else:
                return await asyncio.get_event_loop().run_in_executor(None, task)
    
    results = await asyncio.gather(
        *[run_with_semaphore(task) for task in tasks],
        return_exceptions=True
    )
    
    return results

class BatchProcessor:
    """Process items in batches"""
    
    def __init__(self, batch_size: int = 10, process_func: Optional[Callable] = None):
        self.batch_size = batch_size
        self.process_func = process_func
        self.current_batch = []
        self.results = []
    
    async def add_item(self, item: Any):
        """Add item to batch"""
        self.current_batch.append(item)
        
        if len(self.current_batch) >= self.batch_size:
            await self.process_batch()
    
    async def process_batch(self):
        """Process current batch"""
        if not self.current_batch:
            return
        
        if self.process_func:
            if asyncio.iscoroutinefunction(self.process_func):
                result = await self.process_func(self.current_batch)
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.process_func,
                    self.current_batch
                )
            
            self.results.append(result)
        
        self.current_batch = []
    
    async def flush(self):
        """Process remaining items"""
        await self.process_batch()
    
    def get_results(self) -> List[Any]:
        """Get all results"""
        return self.results