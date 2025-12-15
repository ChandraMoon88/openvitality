# src/core/system_health_monitor.py
"""
The "doctor for the AI" - continuously monitors the health of the system
and its dependencies, enabling self-healing and circuit breaking.
"""
import asyncio
import psutil
from typing import Dict, Any

# Placeholder imports
# from . import config, logger
# import redis.asyncio as redis
# import asyncpg # For postgres
# from .load_balancer import LoadBalancer

class SystemHealthMonitor:
    def __init__(self, check_interval_seconds: int = 60):
        self.check_interval = check_interval_seconds
        self.status: Dict[str, Any] = {}
        self._is_running = False
        self._task = None
        # self.load_balancer = LoadBalancer(...) # Needs a reference to the LB
        print("SystemHealthMonitor initialized.")

    async def _perform_one_check_cycle(self):
        """Runs one cycle of all health checks and updates the status."""
        # logger.debug("Running system health checks...")
        results = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_llm_api(),
            self.check_disk_space(),
            self.check_memory_usage(),
            return_exceptions=True # Prevent one failed check from stopping others
        )
        
        # Update status
        check_names = ["database", "redis", "llm_api", "disk", "memory"]
        for name, result in zip(check_names, results):
            if isinstance(result, Exception):
                self.status[name] = {"status": "unhealthy", "error": str(result)}
                # logger.error(f"Health check '{name}' failed: {result}")
            else:
                self.status[name] = result

    async def _run_checks(self):
        """The main loop that periodically runs all health checks."""
        while self._is_running:
            await self._perform_one_check_cycle()
            await asyncio.sleep(self.check_interval)

    def start(self):
        """Starts the monitoring loop in a background task."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._run_checks())
            # logger.info("System health monitor started.")

    def stop(self):
        """Stops the monitoring loop."""
        self._is_running = False
        if self._task:
            self._task.cancel()
            # logger.info("System health monitor stopped.")

    def get_status(self) -> Dict[str, Any]:
        """Returns the latest health status."""
        return self.status

    # --- Individual Health Checks ---

    async def check_database(self) -> Dict:
        # conn = await asyncpg.connect(config.database.db_url)
        # await conn.fetchval("SELECT 1")
        # await conn.close()
        return {"status": "healthy"}

    async def check_redis(self) -> Dict:
        # client = redis.from_url(config.database.redis_url)
        # await client.ping()
        # await client.close()
        return {"status": "healthy"}

    async def check_llm_api(self) -> Dict:
        # A lightweight test call to the Gemini API
        # try:
        #     resource = self.load_balancer.get_next_resource()
        #     # await make_test_call(resource.key)
        #     return {"status": "healthy", "active_key": f"...{resource.key[-4:]}"}
        # except Exception as e:
        #     # If this fails, the load balancer's circuit breaker will handle it
        #     return {"status": "unhealthy", "error": str(e)}
        return {"status": "healthy"}


    async def check_disk_space(self) -> Dict:
        usage = psutil.disk_usage('/')
        percent_free = 100 - usage.percent
        if percent_free < 10:
            status = "unhealthy"
        else:
            status = "healthy"
        return {"status": status, "free_percent": round(percent_free, 2)}

    async def check_memory_usage(self) -> Dict:
        usage = psutil.virtual_memory()
        if usage.percent > 90:
            status = "unhealthy"
        else:
            status = "healthy"
        return {"status": status, "used_percent": usage.percent}
