import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import the FastAPI app directly from main.py
# We need to mock APIManager and its methods before importing app,
# as app.on_event("startup") will try to initialize APIManager.
with patch('src.core.main.APIManager') as MockAPIManager:
    # Configure the mock APIManager and its instance
    mock_api_manager_instance = MockAPIManager.return_value
    mock_api_manager_instance.initialize = MagicMock(return_value=None)
    mock_api_manager_instance.close = MagicMock(return_value=None)
    mock_api_manager_instance.populate_from_yaml = MagicMock(return_value=None)
    
    # Mock os.getenv to control API_MANAGER_DB_URL and API_MANAGER_POPULATE_FROM_YAML
    with patch.dict(os.environ, {
        "API_MANAGER_DB_URL": "postgresql://test:test@localhost:5432/test",
        "API_MANAGER_POPULATE_FROM_YAML": "0" # Do not populate from YAML by default
    }):
        from src.core.main import app

@pytest.mark.asyncio
async def test_health_check():
    """Test the /health endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["api_manager_initialized"] is True

@pytest.mark.asyncio
async def test_root_endpoint():
    """Test the / endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to the Free AI Hospital API. See /docs for documentation."

@pytest.mark.asyncio
async def test_chat_endpoint():
    """Test the /v1/chat endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/v1/chat", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["response"] == "This is a placeholder text response."

@pytest.mark.asyncio
async def test_voice_endpoint():
    """Test the /v1/voice endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/v1/voice", content=b"audio_blob_data")
    assert response.status_code == 200
    assert response.json()["response"] == "This is a placeholder audio response."

@pytest.mark.asyncio
async def test_websocket_endpoint():
    """Test the /v1/stream websocket endpoint."""
    async with AsyncClient(app=app, base_url="ws://test") as ac:
        async with ac.websocket_connect("/v1/stream") as websocket:
            await websocket.send_bytes(b"audio_chunk_data")
            message = await websocket.receive_text()
            assert message == "Received audio chunk."
            await websocket.close()

# Test startup and shutdown events more thoroughly
@pytest.mark.asyncio
async def test_api_manager_startup_and_shutdown():
    """
    Test that APIManager's initialize and close methods are called
    during app startup and shutdown.
    """
    with patch('src.core.main.APIManager') as MockAPIManager:
        mock_api_manager_instance = MockAPIManager.return_value
        mock_api_manager_instance.initialize = MagicMock(return_value=None)
        mock_api_manager_instance.close = MagicMock(return_value=None)
        mock_api_manager_instance.populate_from_yaml = MagicMock(return_value=None)

        # We need to re-import app within this patch context to ensure the
        # app instance picks up the mocked APIManager
        from src.core.main import app as app_patched

        async with AsyncClient(app=app_patched, base_url="http://test") as ac:
            # The app startup event will trigger initialize()
            await ac.get("/health")
            MockAPIManager.assert_called_once()
            mock_api_manager_instance.initialize.assert_called_once()

        # The app shutdown event should trigger close()
        mock_api_manager_instance.close.assert_called_once()

@pytest.mark.asyncio
async def test_api_manager_populate_on_startup():
    """Test that APIManager populate_from_yaml is called if env var is set."""
    with patch('src.core.main.APIManager') as MockAPIManager:
        mock_api_manager_instance = MockAPIManager.return_value
        mock_api_manager_instance.initialize = MagicMock(return_value=None)
        mock_api_manager_instance.close = MagicMock(return_value=None)
        mock_api_manager_instance.populate_from_yaml = MagicMock(return_value=None)
        
        # Mock os.getenv to enable YAML population
        with patch.dict(os.environ, {
            "API_MANAGER_DB_URL": "postgresql://test:test@localhost:5432/test",
            "API_MANAGER_POPULATE_FROM_YAML": "1",
            "API_DB_YAML_PATH": "/path/to/mock_api_db.yaml" # Mock a path
        }):
            # Mock os.path.exists to return True for the mocked yaml path
            with patch('os.path.exists', return_value=True):
                # Re-import app to pick up new env vars and mocks
                from src.core.main import app as app_populate_patched
                async with AsyncClient(app=app_populate_patched, base_url="http://test") as ac:
                    await ac.get("/health")
                    mock_api_manager_instance.populate_from_yaml.assert_called_once_with("/path/to/mock_api_db.yaml")

@pytest.mark.asyncio
async def test_api_manager_init_failure_does_not_halt_app():
    """Test that APIManager initialization failure doesn't prevent app from starting."""
    with patch('src.core.main.APIManager') as MockAPIManager:
        # Make initialize raise an exception
        mock_api_manager_instance = MockAPIManager.return_value
        mock_api_manager_instance.initialize = MagicMock(side_effect=Exception("DB connection failed"))
        mock_api_manager_instance.close = MagicMock(return_value=None)

        with patch.dict(os.environ, {
            "API_MANAGER_DB_URL": "invalid_db_url",
            "API_MANAGER_POPULATE_FROM_YAML": "0"
        }):
            from src.core.main import app as app_failing_init
            async with AsyncClient(app=app_failing_init, base_url="http://test") as ac:
                response = await ac.get("/health")
                assert response.status_code == 200
                assert response.json()["status"] == "healthy"
                assert response.json()["api_manager_initialized"] is False # Should be False due to init failure
                MockAPIManager.assert_called_once()
                mock_api_manager_instance.initialize.assert_called_once()
