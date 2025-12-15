# src/core/orchestrator.py
"""
The central conductor of the AI system.
"""
import os
import asyncio
import time
from typing import Dict, Any, Optional
import logging

# Removed direct genai import as it will be handled by LLMFactory
# import google.generativeai as genai

from src.core.database_manager import DatabaseManager
from src.core.session_manager import SessionManager
from src.intelligence.llm_factory import LLMFactory
from src.intelligence.llm_interface import LLMConfig, LLMInterface

logger = logging.getLogger(__name__)

class Orchestrator:
    def __init__(self, db_url: str):
        """
        Initializes the Orchestrator and its core components.
        
        Args:
            db_url: The connection string for the application's PostgreSQL database.
        """
        self.db_manager = DatabaseManager(db_url)
        self.session_manager = SessionManager(self.db_manager)
        
        # Configure the LLM client using LLMFactory
        llm_provider_name = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.llm_provider: Optional[LLMInterface] = None

        if llm_provider_name == "gemini":
            gemini_api_key = os.getenv("GEMINI_API_KEY")
            logger.info(f"Attempting to initialize LLM with GEMINI_API_KEY status: {'set' if gemini_api_key else 'not set'}")

            if gemini_api_key:
                try:
                    gemini_model_name = os.getenv("GEMINI_MODEL_NAME", "gemini-pro")
                    self.llm_config = LLMConfig(model=gemini_model_name, temperature=0.7, max_tokens=200) # Default config
                    self.llm_provider = LLMFactory.get_llm("gemini", self.llm_config.model, config=self.llm_config)
                    logger.info("Orchestrator initialized successfully with Google Gemini via LLMFactory.")
                except Exception as e:
                    logger.critical(f"Failed to configure Gemini client via LLMFactory. Error: {e}", exc_info=True)
                    self.llm_provider = None
            else:
                logger.warning("Orchestrator initialized without a Gemini LLM. GEMINI_API_KEY not found or is empty.")
        elif llm_provider_name == "huggingface":
            hf_api_token = os.getenv("HF_API_TOKEN")
            hf_model_id = os.getenv("HF_MODEL_ID", "distilgpt2") # Default to a small, generally available HF model
            logger.info(f"Attempting to initialize LLM with HuggingFace (Model: {hf_model_id}, API_TOKEN status: {'set' if hf_api_token else 'not set'})")

            if hf_api_token:
                try:
                    self.llm_config = LLMConfig(model=hf_model_id, temperature=0.7, max_tokens=200) # Default config
                    self.llm_provider = LLMFactory.get_llm("huggingface", self.llm_config.model, config=self.llm_config, use_inference_api=True)
                    logger.info(f"Orchestrator initialized successfully with HuggingFace Inference API for model {hf_model_id}.")
                except Exception as e:
                    logger.critical(f"Failed to configure HuggingFace client via LLMFactory. Error: {e}", exc_info=True)
                    self.llm_provider = None
            else:
                logger.warning("Orchestrator initialized without a HuggingFace LLM. HF_API_TOKEN not found or is empty.")
        else:
            logger.critical(f"Unknown LLM_PROVIDER specified: {llm_provider_name}. Please set LLM_PROVIDER to 'gemini' or 'huggingface'.")
            self.llm_provider = None
        
    async def _get_llm_response(self, text_input: str) -> str:
        """
        Gets a response from the configured LLM provider.
        """
        fallback_response = f"I received your message: '{text_input}', but my AI capabilities are not configured."

        if not self.llm_provider:
            logger.error("LLM provider not available.")
            return fallback_response

        try:
            # Generate content using the LLM provider's generate_text method
            response = self.llm_provider.generate_text(text_input, self.llm_config)
            return response.generated_text
        except Exception as e:
            logger.error(f"Call to LLM provider failed: {e}", exc_info=True)
            return fallback_response


    async def handle_text_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for processing text-based requests.
        """
        start_time = time.time()
        
        external_user_id = data.get("external_user_id")
        if not external_user_id:
            return {"error": "external_user_id is required."}
            
        text_input = data.get("text", "")
        session_context = data.get("session_context", {})

        session_id = await self.session_manager.get_or_create_session(
            external_user_id=external_user_id,
            session_context=session_context
        )
        
        if not session_id:
            return {"error": "Failed to create or retrieve a session."}

        await self.session_manager.log_turn(
            session_id=session_id,
            actor="user",
            text=text_input
        )
        
        try:
            agent_response = await self._get_llm_response(text_input)
            
            await self.session_manager.log_turn(
                session_id=session_id,
                actor="ai",
                text=agent_response
            )
            
            processing_time = time.time() - start_time
            logger.info(f"Request for session {session_id} processed in {processing_time:.2f}s")

            return {"response": agent_response, "session_id": str(session_id), "agent": "google_gemini_direct"}

        except Exception as e:
            logger.error(f"Orchestrator error for session {session_id}: {e}", exc_info=True)
            return {"error": "An internal error occurred.", "session_id": str(session_id)}

    async def connect_services(self):
        """
        Establishes connections to external services, primarily the database.
        """
        await self.db_manager.initialize()
        logger.info("Orchestrator connected to database.")

    async def close_services(self):
        """
        Closes connections to external services.
        """
        await self.db_manager.close()
        logger.info("Orchestrator disconnected from database.")
