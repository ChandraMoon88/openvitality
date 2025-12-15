# src/core/main.py
"""
The main entry point for the FastAPI application.

This file defines the FastAPI app, configures middleware, sets up startup/shutdown events,
and creates the API endpoints for chat, voice, and health checks.
"""
import os
import time
import uuid
import logging
from datetime import datetime
from dotenv import load_dotenv

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from src.core.orchestrator import Orchestrator
from src.core.api_manager import APIManager
from src.telephony.sip_manager import SIPManager
# from .error_handler_global import global_exception_handler
# from .system_health_monitor import SystemHealth

# Load environment variables from .env file
load_dotenv()

# --- Logging Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- FastAPI App Initialization ---
app = FastAPI(
    title="OpenVitality AI API",
    version="0.1.0",
    description="API for providing AI-driven healthcare consultations.",
)

# --- Middleware Configuration ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Logs incoming requests and their processing time."""
    request_id = str(uuid.uuid4())
    logger.info(f"rid={request_id} start request path={request.url.path}")
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = f'{process_time:.2f}'
    logger.info(f"rid={request_id} completed_in={formatted_process_time}ms status_code={response.status_code}")
    
    return response

# --- Startup and Shutdown Events ---
@app.on_event("startup")
async def startup_event():
    """
    Actions to perform on application startup.
    - Initialize Orchestrator and its database connections
    """
    # Initialize Orchestrator (for application logic and DB)
    app_db_url = os.getenv("APPLICATION_DB_URL")
    app.state.orchestrator = None
    if app_db_url:
        try:
            app.state.orchestrator = Orchestrator(db_url=app_db_url)
            await app.state.orchestrator.connect_services()
        except Exception as e:
            logger.critical(f"Orchestrator initialization failed: {e}", exc_info=True)
    else:
        logger.warning("APPLICATION_DB_URL not set. Orchestrator will not be available.")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Actions to perform on application shutdown.
    - Gracefully close database connections
    """
    # Close Orchestrator connections
    if getattr(app.state, "orchestrator", None):
        await app.state.orchestrator.close_services()

    logger.info("Application shutdown complete.")

# --- Global Exception Handler ---
# @app.exception_handler(Exception)
# async def exception_callback(request: Request, exc: Exception):
#     return await global_exception_handler(request, exc)

# --- API Endpoints ---
@app.get("/health", tags=["System"]) 
async def health_check():
    """
    Provides a simple health check endpoint to verify the API is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "orchestrator_ready": bool(getattr(app.state, "orchestrator", None)),
    }

@app.get("/", tags=["System"])
async def root():
    """
    Root endpoint with a link to the API documentation.
    """
    return {"message": "Welcome to the OpenVitality AI API. See /docs for documentation."}

@app.get("/v1/test-gemini", tags=["Tests"])
async def test_gemini_key_loading(request: Request):
    """
    Tests if the Gemini API key was loaded from the environment correctly.
    """
    orchestrator: Orchestrator = getattr(app.state, "orchestrator", None)
    if not orchestrator:
        return JSONResponse(status_code=503, content={"error": "Orchestrator is not available."})
    
    if orchestrator.llm_model:
        return {"status": "SUCCESS", "message": "Gemini client was successfully configured in the Orchestrator."}
    else:
        return JSONResponse(status_code=404, content={"status": "FAILURE", "message": "Gemini client not configured. Check GEMINI_API_KEY."})
        

@app.get("/v1/test-sip", tags=["Tests"])
async def test_sip_config_loading(request: Request):
    """
    Tests if the SIP credentials were loaded from the environment correctly.
    """
    sip_manager: SIPManager = getattr(app.state, "sip_manager", None)
    if not sip_manager:
        return JSONResponse(status_code=503, content={"error": "SIPManager is not available. Check environment variables."})
    
    return {"status": "SUCCESS", "details": sip_manager.get_status()}


@app.post("/v1/chat", tags=["AI Interaction"])
async def chat_endpoint(request: Request):
    """
    Handles text-based chat interactions.
    Requires a JSON body with 'external_user_id' and 'text'.
    """
    orchestrator: Orchestrator = getattr(app.state, "orchestrator", None)
    if not orchestrator:
        return JSONResponse(status_code=503, content={"error": "Orchestrator is not available. Check server configuration."})
        
    data = await request.json()
    response = await orchestrator.handle_text_input(data)
    
    if "error" in response:
        return JSONResponse(status_code=500, content=response)
        
    return JSONResponse(content=response)

@app.post("/v1/voice", tags=["AI Interaction"])
async def voice_endpoint(request: Request):
    """
    Handles voice-based interactions (uploads audio blob).
    """
    audio_blob = await request.body()
    # response_audio = await orchestrator.handle_audio_input(audio_blob)
    return JSONResponse(status_code=501, content={"response": "Voice endpoint not yet implemented."})

@app.websocket("/v1/stream", name="Real-time Voice Stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    Handles real-time, bidirectional voice streaming over WebSockets.
    """
    await websocket.accept()
    try:
        while True:
            audio_chunk = await websocket.receive_bytes()
            # await orchestrator.handle_audio_stream(audio_chunk, websocket)
            await websocket.send_text("Streaming endpoint not yet implemented.")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}", exc_info=True)
        await websocket.close(code=1011, reason="An internal error occurred.")
