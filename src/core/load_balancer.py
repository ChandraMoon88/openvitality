# src/core/load_balancer.py
"""
Distributes requests across multiple API keys or endpoints to maximize
uptime and stay within free tier limits. Implements a circuit breaker
pattern to handle failing resources gracefully.
"""
import time
from typing import List, Dict

# from . import logger

class APIResource:
    """Represents a single API key or endpoint."""
    def __init__(self, key: str, cooldown_period: int = 300):
        self.key = key
        self.is_healthy = True
        self.failure_count = 0
        self.last_failure_time = 0
        self.cooldown_period = cooldown_period

    def record_failure(self):
        """Records a failure for this resource."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        # logger.warning(f"Failure recorded for API key ending in '...{self.key[-4:]}'. Failures: {self.failure_count}")

    def record_success(self):
        """Resets the failure count upon a successful call."""
        if self.failure_count > 0:
            # logger.info(f"API key '...{self.key[-4:]}' is healthy again.")
            self.failure_count = 0
            self.last_failure_time = 0

    def check_health(self):
        """
        Updates the health status. If in cooldown, checks if it can be re-enabled.
        """
        if not self.is_healthy and (time.time() - self.last_failure_time > self.cooldown_period):
            # logger.info(f"Cooldown period ended for API key '...{self.key[-4:]}'. Resetting health status.")
            self.is_healthy = True
            self.failure_count = 0
        return self.is_healthy

class LoadBalancer:
    def __init__(self, api_keys: List[str], max_failures: int = 5):
        """
        Initializes the LoadBalancer with a list of API keys.
        
        Args:
            api_keys: A list of API keys to cycle through.
            max_failures: The number of consecutive failures before opening the circuit.
        """
        if not api_keys:
            raise ValueError("API key list cannot be empty.")
        self.resources = [APIResource(key) for key in api_keys]
        self.max_failures = max_failures
        self.current_index = 0
        print("LoadBalancer initialized.")

    def get_next_resource(self) -> APIResource:
        """
        Gets the next available, healthy resource using a round-robin strategy.
        Implements a circuit breaker to skip unhealthy resources.
        """
        for _ in range(len(self.resources)):
            resource = self.resources[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.resources)

            if resource.check_health():
                # logger.debug(f"Selected API key '...{resource.key[-4:]}' for the next request.")
                return resource

        # If we get here, all resources are unhealthy
        # logger.critical("All API resources are unhealthy!")
        raise RuntimeError("All available API resources are currently failing.")
        
    def report_failure(self, resource: APIResource):
        """Reports a failure for a given resource."""
        resource.record_failure()
        if resource.failure_count >= self.max_failures:
            resource.is_healthy = False
            # logger.error(f"Circuit breaker opened for API key '...{resource.key[-4:]}'. It will be disabled for {resource.cooldown_period}s.")

    def report_success(self, resource: APIResource):
        """Reports a success for a given resource."""
        resource.record_success()

# Example Usage
# async def make_api_call(lb: LoadBalancer):
#     try:
#         resource = lb.get_next_resource()
#         # response = await some_api_library.call(api_key=resource.key)
#         # lb.report_success(resource)
#         # return response
#     except Exception as e:
#         lb.report_failure(resource)
#         # Re-raise or handle the exception
#         raise e
