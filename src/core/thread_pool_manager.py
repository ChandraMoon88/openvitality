# src/core/thread_pool_manager.py
"""
Manages thread and process pools for offloading intensive tasks from the
main async event loop, preventing it from being blocked.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import os

# from . import logger

class ThreadPoolManager:
    def __init__(self, max_io_workers=None, max_cpu_workers=None):
        """
        Initializes the thread and process pools.
        
        Args:
            max_io_workers: Max threads for I/O tasks. Defaults to 2x CPU cores.
            max_cpu_workers: Max processes for CPU tasks. Defaults to number of CPU cores.
        """
        # Rule of thumb for sizing pools
        cpu_cores = os.cpu_count() or 1
        
        if max_io_workers is None:
            max_io_workers = cpu_cores * 2
        if max_cpu_workers is None:
            max_cpu_workers = cpu_cores

        # ThreadPoolExecutor is for I/O-bound tasks (like blocking API calls, file I/O)
        self.io_pool = ThreadPoolExecutor(max_workers=max_io_workers)
        
        # ProcessPoolExecutor is for CPU-bound tasks (like audio transcoding, complex calculations)
        self.cpu_pool = ProcessPoolExecutor(max_workers=max_cpu_workers)
        
        # logger.info(f"ThreadPoolManager initialized with {max_io_workers} I/O workers and {max_cpu_workers} CPU workers.")
        print(f"ThreadPoolManager initialized with {max_io_workers} I/O workers and {max_cpu_workers} CPU workers.")


    async def run_in_io_pool(self, func, *args):
        """
        Runs a blocking I/O function in the thread pool to avoid blocking the event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.io_pool, func, *args)

    async def run_in_cpu_pool(self, func, *args):
        """
        Runs a CPU-intensive function in the process pool.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.cpu_pool, func, *args)

    def shutdown(self):
        """
        Shuts down both pools gracefully.
        """
        # logger.info("Shutting down thread and process pools...")
        self.io_pool.shutdown(wait=True)
        self.cpu_pool.shutdown(wait=True)
        # logger.info("Pools shut down complete.")

# --- Global instance ---
# This makes it easy to access from anywhere in the application.
pool_manager = ThreadPoolManager()

# --- Example Usage ---

# A blocking I/O function
# def blocking_file_read(path):
#     with open(path, 'r') as f:
#         return f.read()

# A CPU-intensive function
# def cpu_heavy_audio_processing(audio_data):
#     # Simulate heavy work
#     # ...
#     return "processed_audio"

# How to use it in an async context
# async def main():
#     # Offload file reading to the I/O pool
#     file_content = await pool_manager.run_in_io_pool(blocking_file_read, "my_file.txt")
    
#     # Offload audio processing to the CPU pool
#     processed_audio = await pool_manager.run_in_cpu_pool(cpu_heavy_audio_processing, b"some_audio_data")
    
#     pool_manager.shutdown()

# This would be integrated into the FastAPI shutdown event.
# In main.py:
# @app.on_event("shutdown")
# async def shutdown_event():
#     pool_manager.shutdown()
