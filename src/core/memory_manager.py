# src/core/memory_manager.py
"""
Manages the AI's short-term and long-term memory to provide context-aware
responses and maintain a persistent medical record.
"""
import chromadb
from cachetools import LRUCache
from typing import Dict, List, Any

# Placeholder imports
# from . import logger, config
# from .llm_service import summarize_conversation

class MemoryManager:
    def __init__(self):
        """Initializes the MemoryManager."""
        # Short-term memory: A simple in-memory cache for the last few exchanges
        self.short_term_memory = LRUCache(maxsize=100) # Caches last 100 sessions' recent history
        
        # Long-term memory: ChromaDB for persistent, searchable vector storage
        # self.client = chromadb.PersistentClient(path=config.database.vector_store_path)
        # self.collection = self.client.get_or_create_collection(name="patient_history")
        
        print("MemoryManager initialized.")

    def get_short_term_context(self, session_id: str) -> List[Dict]:
        """Gets the recent conversation history from RAM."""
        return self.short_term_memory.get(session_id, [])

    def update_short_term_context(self, session_id: str, new_exchange: Dict):
        """Updates the recent conversation history."""
        history = self.get_short_term_context(session_id)
        history.append(new_exchange)
        # Keep only the last 5 exchanges
        self.short_term_memory[session_id] = history[-5:]

    async def summarize_and_store_long_term(self, session: Dict):
        """
        At the end of a conversation, this function summarizes it and stores
        the key medical facts in the long-term vector store.
        """
        patient_id = session['user_phone_hash']
        full_history = session['history']
        
        # Use an LLM to summarize the conversation
        # summary_text = await summarize_conversation(full_history)
        summary_text = "Patient reported fever and fatigue for 3 days. Advised hydration and monitoring." # Placeholder
        
        # Extract key entities (conceptual)
        symptoms = ["fever", "fatigue"]
        recommendations = ["increase fluids", "monitor temperature"]

        storage_document = {
            "date": session['started_at'],
            "summary": summary_text,
            "symptoms": symptoms,
            "recommendations": recommendations,
        }
        
        # Store in ChromaDB
        # self.collection.add(
        #     documents=[summary_text],
        #     metadatas=[{"patient_id": patient_id, "date": session['started_at']}],
        #     ids=[f"{patient_id}_{session['session_id']}"]
        # )
        # logger.info(f"Stored long-term memory for patient {patient_id}.")
        print(f"Stored long-term memory for patient {patient_id}.")

    async def retrieve_long_term_history(self, patient_id: str, query: str) -> List[Dict]:
        """
        When a user calls again, retrieves relevant past medical history
        from the vector store based on the current query.
        """
        # results = self.collection.query(
        #     query_texts=[query],
        #     n_results=3,
        #     where={"patient_id": patient_id}
        # )
        
        # logger.info(f"Retrieved {len(results.get('documents', []))} relevant history documents for patient {patient_id}.")
        # return results.get('metadatas', [])
        print(f"Retrieved long-term history for patient {patient_id}.")
        return [{"summary": "Previously reported a cough."}] # Placeholder

    def schedule_forgetting(self, session_id: str):
        """
        Schedules the deletion of sensitive data according to data retention policies.
        (The actual deletion would be handled by a separate worker process).
        """
        # E.g., add a task to a queue:
        # task_scheduler.add_job('delete_audio_files', run_date=datetime.now() + timedelta(days=7), args=[session_id])
        # task_scheduler.add_job('anonymize_text_logs', run_date=datetime.now() + timedelta(days=30), args=[session_id])
        print(f"Scheduled data forgetting tasks for session {session_id}.")
