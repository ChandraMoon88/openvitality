import sys
import os
import unittest
from unittest.mock import Mock, patch
import asyncio

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.error_handler_global import (
    global_exception_handler,
    safe_execute,
    ValidationError,
    AuthenticationError,
    NetworkError
)

class TestGlobalErrorHandler(unittest.TestCase):

    def test_global_handler_debug_mode(self):
        """Test the global handler's detailed response in debug mode."""
        mock_request = Mock()
        test_exception = ValueError("Test error message")

        # The file has is_debug_mode = True, so we test that path first.
        response = asyncio.run(global_exception_handler(mock_request, test_exception))
        
        self.assertEqual(response.status_code, 500)
        response_body = response.body.decode()
        self.assertIn("An internal server error occurred.", response_body)
        self.assertIn("ValueError", response_body)
        self.assertIn("Test error message", response_body)
        self.assertIn("traceback", response_body)

    @patch('src.core.error_handler_global.is_debug_mode', False)
    def test_global_handler_production_mode(self):
        """Test the global handler's generic response in production mode."""
        mock_request = Mock()
        test_exception = ValueError("Sensitive internal details")
        
        response = asyncio.run(global_exception_handler(mock_request, test_exception))
        
        self.assertEqual(response.status_code, 500)
        response_body = response.body.decode()
        self.assertNotIn("Sensitive internal details", response_body)
        self.assertNotIn("traceback", response_body)
        expected_msg = "We're sorry, something went wrong. Our team has been notified. Please try again later."
        self.assertIn(expected_msg, response_body)

    def test_global_handler_specific_exceptions(self):
        """Test status codes for specific exception types."""
        mock_request = Mock()
        
        # Test ValidationError
        validation_exc = ValidationError("Invalid input")
        response_400 = asyncio.run(global_exception_handler(mock_request, validation_exc))
        self.assertEqual(response_400.status_code, 400)
        
        # Test AuthenticationError
        auth_exc = AuthenticationError("Invalid credentials")
        response_401 = asyncio.run(global_exception_handler(mock_request, auth_exc))
        self.assertEqual(response_401.status_code, 401)

class TestSafeExecuteDecorator(unittest.TestCase):
    
    def test_decorator_success_case(self):
        """Test that the decorator returns the function's result when no exception occurs."""
        
        @safe_execute(default_return="fallback")
        async def successful_func():
            return "success"
            
        result = asyncio.run(successful_func())
        self.assertEqual(result, "success")

    def test_decorator_exception_case(self):
        """Test that the decorator catches an exception and returns the default value."""
        
        @safe_execute(default_return="fallback")
        async def failing_func():
            raise NetworkError("Connection failed")
            
        result = asyncio.run(failing_func())
        self.assertEqual(result, "fallback")
        
    def test_decorator_with_none_default(self):
        """Test the decorator when the default return value is None."""
        
        @safe_execute(default_return=None)
        async def another_failing_func():
            raise ValueError("Something went wrong")
            
        result = asyncio.run(another_failing_func())
        self.assertIsNone(result)

    def test_decorator_preserves_function_metadata(self):
        """Test that the decorator preserves the original function's metadata."""
        
        @safe_execute()
        async def my_original_function():
            """This is my docstring."""
            pass
            
        self.assertEqual(my_original_function.__name__, 'my_original_function')
        self.assertEqual(my_original_function.__doc__, 'This is my docstring.')


if __name__ == '__main__':
    unittest.main()
