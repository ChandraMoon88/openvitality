import sys
import os
import unittest
from unittest.mock import patch
import time

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.load_balancer import LoadBalancer, APIResource

class TestLoadBalancer(unittest.TestCase):

    def setUp(self):
        """Set up a LoadBalancer instance for each test."""
        self.api_keys = ["key1", "key2", "key3"]
        self.lb = LoadBalancer(self.api_keys, max_failures=2)

    def test_init_with_empty_keys(self):
        """Test that initializing with an empty list raises a ValueError."""
        with self.assertRaises(ValueError):
            LoadBalancer([])

    def test_round_robin_get_next_resource(self):
        """Test that resources are returned in a round-robin fashion."""
        resource1 = self.lb.get_next_resource()
        self.assertEqual(resource1.key, "key1")
        resource2 = self.lb.get_next_resource()
        self.assertEqual(resource2.key, "key2")
        resource3 = self.lb.get_next_resource()
        self.assertEqual(resource3.key, "key3")
        # It should wrap around
        resource4 = self.lb.get_next_resource()
        self.assertEqual(resource4.key, "key1")

    def test_circuit_breaker_opens_after_max_failures(self):
        """Test that a resource becomes unhealthy after max_failures."""
        resource = self.lb.get_next_resource() # Get key1
        self.assertTrue(resource.is_healthy)

        # Report 2 failures (max_failures = 2)
        self.lb.report_failure(resource)
        self.lb.report_failure(resource)

        # The resource should now be unhealthy
        self.assertFalse(resource.is_healthy)
        
        # The next call to get_next_resource should skip the unhealthy one
        next_resource = self.lb.get_next_resource()
        self.assertEqual(next_resource.key, "key2")

    def test_unhealthy_resource_is_skipped(self):
        """Test that an unhealthy resource is skipped in the rotation."""
        # Manually mark key1 as unhealthy
        resource = self.lb.resources[0]
        resource.is_healthy = False
        resource.last_failure_time = time.time()
        
        # The next resource should be key2, not key1
        resource = self.lb.get_next_resource()
        self.assertEqual(resource.key, "key2")

    @patch('time.time')
    def test_resource_becomes_healthy_after_cooldown(self, mock_time):
        """Test that a resource is re-enabled after its cooldown period."""
        resource = self.lb.resources[0]
        cooldown = resource.cooldown_period
        
        # Initial time
        mock_time.return_value = 1000
        
        # Fail the resource enough to open the circuit
        self.lb.report_failure(resource)
        self.lb.report_failure(resource)
        
        # At this point, last_failure_time is 1000
        self.assertEqual(resource.last_failure_time, 1000)
        resource.is_healthy = False # Manually open circuit

        # Move time forward, but still within the cooldown
        mock_time.return_value = 1000 + cooldown - 10
        self.assertFalse(resource.check_health())

        # Move time forward past the cooldown period
        mock_time.return_value = 1000 + cooldown + 10
        self.assertTrue(resource.check_health())
        # Check that failure count is reset
        self.assertEqual(resource.failure_count, 0)
        
    def test_report_success_resets_failures(self):
        """Test that a success report resets the failure count for a resource."""
        resource = self.lb.resources[0]
        
        # Record one failure
        self.lb.report_failure(resource)
        self.assertEqual(resource.failure_count, 1)

        # Report a success
        self.lb.report_success(resource)
        self.assertEqual(resource.failure_count, 0)

    def test_runtime_error_when_all_resources_fail(self):
        """Test that a RuntimeError is raised if all resources are unhealthy."""
        # Mark all resources as unhealthy
        for resource in self.lb.resources:
            resource.is_healthy = False
            resource.last_failure_time = time.time()
        
        with self.assertRaises(RuntimeError):
            self.lb.get_next_resource()


if __name__ == '__main__':
    unittest.main()
