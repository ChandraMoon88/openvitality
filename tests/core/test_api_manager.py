import sys
import os
import unittest
from unittest.mock import AsyncMock, patch, Mock
from cryptography.fernet import Fernet

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.api_manager import APIManager

# Generate a single valid key to be used for all tests in this file
# This key is in bytes, and we decode it to a string for the APIManager
TEST_FERNET_KEY = Fernet.generate_key().decode('utf-8')

class TestAPIManagerLogic(unittest.TestCase):
    """
    Tests the pure logic methods of the APIManager that do not require
    database or network connections.
    """

    def setUp(self):
        """Instantiate the manager with a valid encryption key."""
        self.manager = APIManager(db_url="dummy_url", encryption_key=TEST_FERNET_KEY)

    def test_parse_rate_limits(self):
        """Test the parsing of rate limit strings."""
        self.assertEqual(
            self.manager._parse_rate_limits("100 requests/minute"),
            {'per_second': None, 'per_minute': 100, 'per_hour': None, 'per_day': None}
        )
        self.assertEqual(
            self.manager._parse_rate_limits("5/sec, 1000/day"),
            {'per_second': 5, 'per_minute': None, 'per_hour': None, 'per_day': 1000}
        )
        self.assertEqual(
            self.manager._parse_rate_limits("Unlimited"),
            {'per_second': None, 'per_minute': None, 'per_hour': None, 'per_day': None}
        )
        self.assertEqual(
            self.manager._parse_rate_limits("50 per hour"),
            {'per_second': None, 'per_minute': None, 'per_hour': 50, 'per_day': None}
        )
        self.assertEqual(
            self.manager._parse_rate_limits(""),
            {'per_second': None, 'per_minute': None, 'per_hour': None, 'per_day': None}
        )

    def test_extract_provider(self):
        """Test the extraction of provider names from API names."""
        self.assertEqual(self.manager._extract_provider("Google Gemini Pro"), "Google")
        self.assertEqual(self.manager._extract_provider("Azure Speech Services"), "Microsoft")
        self.assertEqual(self.manager._extract_provider("OpenAI Whisper v3"), "OpenAI")
        self.assertEqual(self.manager._extract_provider("Groq Whisper"), "Groq")
        self.assertEqual(self.manager._extract_provider("Some Random API"), "Unknown")
        self.assertEqual(self.manager._extract_provider("Official WHO Feed"), "WHO")

class TestAPIManagerDB(unittest.IsolatedAsyncioTestCase):
    """
    Tests the database interaction methods of the APIManager using mocks.
    """

    @patch('asyncpg.create_pool', new_callable=AsyncMock)
    async def asyncSetUp(self, mock_create_pool):
        """Set up a mocked database pool and an APIManager instance."""
        self.manager = APIManager(db_url="dummy_url_for_async_tests",
                                  encryption_key=TEST_FERNET_KEY)

        # Configure the mock pool that will be "returned" by asyncpg.create_pool
        self.mock_pool = AsyncMock()
        mock_create_pool.return_value = self.mock_pool

        # The pool.acquire() method should be a REGULAR method that RETURNS an async context manager.
        # We replace the default AsyncMock for 'acquire' with a standard Mock.
        self.mock_pool.acquire = Mock()

        # This is the async context manager that acquire() will return.
        mock_context_manager = AsyncMock()
        self.mock_conn = AsyncMock()
        mock_context_manager.__aenter__.return_value = self.mock_conn
        self.mock_pool.acquire.return_value = mock_context_manager

        # We need to manually call initialize because it's not in the constructor.
        # This will call the patched asyncpg.create_pool and set self.manager.pool
        await self.manager.initialize()


    async def test_add_and_get_api_credential(self):
        """Test the encryption and decryption flow for API credentials."""
        api_name = "test_api"
        credential_name = "api_key"
        credential_value = "my_secret_key_12345"
        
        # Mock the database calls
        self.mock_conn.fetchval.return_value = 1 # Mock returning the api_id
        
        # This part needs to be synchronous for the test setup
        encrypted_value_bytes = self.manager.cipher.encrypt(credential_value.encode())
        
        self.mock_conn.fetchrow.return_value = {
            # Simulate fetching the encrypted value back from the DB
            'credential_value': encrypted_value_bytes.decode('utf-8')
        }
        
        # 1. Add the credential
        await self.manager.add_api_credential(api_name, credential_name, credential_value)
        
        # Assert that the DB insert was called
        self.mock_conn.execute.assert_called_once()
        
        # 2. Get the credential back
        decrypted_key = await self.manager.get_api_credential(api_name, credential_name)
        
        # Assert that we got the original secret back
        self.assertEqual(decrypted_key, credential_value)
        
    async def test_get_nonexistent_credential(self):
        """Test that getting a non-existent credential returns None."""
        self.mock_conn.fetchrow.return_value = None
        
        decrypted_key = await self.manager.get_api_credential("nonexistent_api")
        self.assertIsNone(decrypted_key)

    async def asyncTearDown(self):
        if self.manager._http_session:
            await self.manager.close()


if __name__ == '__main__':
    unittest.main()