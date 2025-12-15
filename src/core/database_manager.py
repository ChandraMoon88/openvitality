"""
OpenVitality AI - Application Database Manager
=================================================
This module provides a centralized interface for all interactions
with the application's core PostgreSQL database, which stores user data,
sessions, dialogue history, and other application state.
"""

import asyncio
from typing import Optional, Dict, List, Any
import asyncpg
import logging
import json
from uuid import UUID

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Handles all CRUD operations for the application's PostgreSQL database.
    """
    
    def __init__(self, db_url: str):
        """
        Initialize the Database Manager.
        
        Args:
            db_url: PostgreSQL connection string for the application database.
                   Example: "postgresql://user:pass@localhost:5432/application_db"
        """
        self.db_url = db_url
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """
        Initialize the database connection pool.
        Call this before using the database manager.
        """
        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=5,
                max_size=20,
                command_timeout=60,
                init=self._setup_json_codec
            )
            logger.info("Application Database Manager initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize database connection pool: {e}", exc_info=True)
            raise

    async def _setup_json_codec(self, connection):
        """Set up JSON/JSONB codecs for asyncpg."""
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        await connection.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )

    async def close(self):
        """Clean up resources."""
        if self.pool:
            await self.pool.close()
            logger.info("Application Database Manager connection pool closed.")

    # =========================================================================
    # User Management
    # =========================================================================
    
    async def get_or_create_user(self, external_id: str, profile: Dict = None) -> Optional[UUID]:
        """
        Get an existing user by their external ID, or create a new one.
        
        Args:
            external_id: The unique external identifier for the user.
            profile: A JSON-compatible dict with user profile info if creating.
            
        Returns:
            The UUID of the user.
        """
        async with self.pool.acquire() as conn:
            user_id = await conn.fetchval("SELECT id FROM users WHERE external_id = $1", external_id)
            if user_id:
                return user_id
            
            # User does not exist, create them
            return await conn.fetchval(
                "INSERT INTO users (external_id, profile) VALUES ($1, $2) RETURNING id",
                external_id, profile or {}
            )

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(self, user_id: UUID, context: Dict = None) -> Optional[UUID]:
        """
        Create a new conversation session for a user.
        
        Args:
            user_id: The UUID of the user starting the session.
            context: A JSON-compatible dict with session context.
        
        Returns:
            The UUID of the new session.
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO sessions (user_id, session_context) VALUES ($1, $2) RETURNING id",
                user_id, context or {}
            )

    async def end_session(self, session_id: UUID, status: str = 'completed'):
        """
        Mark a session as ended.
        
        Args:
            session_id: The UUID of the session to end.
            status: The final status of the session.
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE sessions SET ended_at = NOW(), status = $1 WHERE id = $2",
                status, session_id
            )

    # =========================================================================
    # Dialogue Logging
    # =========================================================================

    async def log_dialogue_turn(self, session_id: UUID, actor: str, text: str, **kwargs) -> Optional[UUID]:
        """
        Log a single turn of conversation.
        
        Args:
            session_id: The session this turn belongs to.
            actor: Who is speaking ('user' or 'ai').
            text: The content of the message.
            **kwargs: Additional fields like language, intent, entities, etc.
            
        Returns:
            The UUID of the newly created log entry.
        """
        fields = ["session_id", "actor", "text"]
        values = [session_id, actor, text]
        
        for key, value in kwargs.items():
            fields.append(key)
            values.append(value)
            
        query = f"""
            INSERT INTO dialogue_log ({', '.join(fields)})
            VALUES ({', '.join(f'${i+1}' for i in range(len(values)))})
            RETURNING id
        """
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *values)

    async def get_dialogue_history(self, session_id: UUID, limit: int = 20) -> List[Dict]:
        """
        Retrieve the recent dialogue history for a session.
        
        Args:
            session_id: The UUID of the session.
            limit: The maximum number of turns to retrieve.
            
        Returns:
            A list of dialogue turns, ordered from oldest to newest.
        """
        query = """
            SELECT actor, text, timestamp
            FROM dialogue_log
            WHERE session_id = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, session_id, limit)
            # Reverse to return in chronological order
            return [dict(row) for row in reversed(rows)]

    # =========================================================================
    # State Management
    # =========================================================================

    async def save_state(self, session_id: UUID, state: str, payload: Dict = None):
        """
        Save the current state of the state machine for a session.
        
        Args:
            session_id: The session to save state for.
            state: The name of the current state.
            payload: JSON-compatible data associated with the state.
        """
        query = """
            INSERT INTO state_machine_data (session_id, current_state, state_payload)
            VALUES ($1, $2, $3)
            ON CONFLICT (session_id) DO UPDATE SET
                current_state = EXCLUDED.current_state,
                state_payload = EXCLUDED.state_payload,
                updated_at = NOW()
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, session_id, state, payload or {})

    async def get_state(self, session_id: UUID) -> Optional[Dict]:
        """
        Retrieve the last saved state for a session.
        
        Args:
            session_id: The session to retrieve state for.
            
        Returns:
            A dictionary containing the state and payload, or None.
        """
        query = "SELECT current_state, state_payload FROM state_machine_data WHERE session_id = $1"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, session_id)
            return dict(row) if row else None


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

async def main():
    """
    Example usage of the DatabaseManager.
    """
    
    # NOTE: Replace with your actual application database URL
    db_manager = DatabaseManager(
        db_url="postgresql://user:password@localhost:5432/application_db"
    )
    await db_manager.initialize()
    
    try:
        # 1. Create a user
        user_id = await db_manager.get_or_create_user(
            external_id="user-12345",
            profile={"name": "Jane Doe", "language": "en"}
        )
        print(f"Got user with ID: {user_id}")
        
        # 2. Start a session
        session_id = await db_manager.create_session(
            user_id,
            context={"channel": "web"}
        )
        print(f"Started session with ID: {session_id}")
        
        # 3. Log conversation turns
        await db_manager.log_dialogue_turn(
            session_id, "user", "Hello, I have a fever.",
            language="en",
            intent={"name": "symptom_report", "confidence": 0.95}
        )
        await db_manager.log_dialogue_turn(
            session_id, "ai", "I understand. How long have you had the fever?"
        )
        
        # 4. Retrieve history
        history = await db_manager.get_dialogue_history(session_id)
        print("\nDialogue History:")
        for turn in history:
            print(f"  {turn['actor']}: {turn['text']}")
            
        # 5. Save state machine state
        await db_manager.save_state(session_id, "AwaitingDuration", {"symptom": "fever"})
        print("\nSaved state.")
        
        # 6. Retrieve state
        state = await db_manager.get_state(session_id)
        print(f"Retrieved state: {state}")
        
        # 7. End the session
        await db_manager.end_session(session_id)
        print("\nSession ended.")
        
    except Exception as e:
        logger.error(f"An error occurred during the example run: {e}")
        
    finally:
        await db_manager.close()


if __name__ == '__main__':
    # This requires a running PostgreSQL instance with the application schema.
    # You would typically not run this directly but import the manager into your main application.
    # To run for testing:
    # 1. Create a PostgreSQL database (e.g., 'application_db')
    # 2. Run the `database/application_schema.sql` script against it.
    # 3. Set the correct DB URL in the main() function above.
    # 4. Run `python src/core/database_manager.py`
    pass
    # asyncio.run(main())
