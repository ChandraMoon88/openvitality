# src/core/session_manager.py
"""
Manages user sessions using the persistent application database.

This module provides a SessionManager class that acts as a high-level
interface for creating, retrieving, and managing user sessions by
interacting with the DatabaseManager. This ensures that sessions are
persistent, scalable, and can be shared across multiple application
instances.
"""
from uuid import UUID
from typing import Dict, Any, Optional
import logging

from src.core.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Handles the lifecycle of user sessions by interfacing with the database.
    """
    def __init__(self, db_manager: DatabaseManager):
        """
        Initializes the SessionManager with a database manager instance.
        
        Args:
            db_manager: An initialized instance of the DatabaseManager.
        """
        self.db = db_manager

    async def get_or_create_session(self, external_user_id: str, 
                                    session_context: Dict = None) -> Optional[UUID]:
        """
        Retrieves an active session for a user or creates a new one.
        
        This is the primary entry point for handling a user interaction.
        
        Args:
            external_user_id: The unique external identifier for the user 
                              (e.g., a hashed phone number).
            session_context: Additional context for a new session.
            
        Returns:
            The UUID of the active or newly created session.
        """
        try:
            # 1. Get or create the user
            user_id = await self.db.get_or_create_user(external_id=external_user_id)
            if not user_id:
                logger.error(f"Failed to get or create user for external_id: {external_user_id}")
                return None

            # 2. For simplicity, we'll create a new session for each interaction for now.
            #    A more advanced implementation would look for an existing 'active' session.
            session_id = await self.db.create_session(user_id, context=session_context)
            if not session_id:
                logger.error(f"Failed to create session for user_id: {user_id}")
                return None

            logger.info(f"Started new session {session_id} for user {user_id}")
            return session_id
        except Exception as e:
            logger.critical(f"Error during session creation for user {external_user_id}: {e}", exc_info=True)
            return None

    async def get_session_data(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieves all relevant data for a given session, including history.
        This reconstructs the 'session object' that other parts of the app can use.
        
        Args:
            session_id: The UUID of the session to retrieve.
        
        Returns:
            A dictionary containing session data, or None if not found.
        """
        # This can be expanded to fetch more details from users table, etc.
        session_row = await self.db.pool.fetchrow("SELECT * FROM sessions WHERE id = $1", session_id)
        if not session_row:
            return None
        
        history = await self.db.get_dialogue_history(session_id, limit=50)
        state = await self.db.get_state(session_id)
        
        session_data = dict(session_row)
        session_data['history'] = history
        session_data['state'] = state or {}
        
        return session_data

    async def end_session(self, session_id: UUID, final_status: str = "completed"):
        """
        Marks a session as completed or terminated.
        
        Args:
            session_id: The UUID of the session to end.
            final_status: The reason for the session ending.
        """
        logger.info(f"Ending session {session_id} with status '{final_status}'")
        await self.db.end_session(session_id, status=final_status)

    async def log_turn(self, session_id: UUID, actor: str, text: str, **kwargs):
        """
        A convenience method to log a dialogue turn.
        
        Args:
            session_id: The session to log against.
            actor: 'user' or 'ai'.
            text: The message content.
            **kwargs: Any additional metadata to log (e.g., intent, entities).
        """
        await self.db.log_dialogue_turn(session_id, actor, text, **kwargs)

    async def save_state(self, session_id: UUID, state: str, payload: Dict):
        """
        A convenience method to save the state machine's current state.
        """
        await self.db.save_state(session_id, state, payload)