# src/intelligence/context_builder.py

from typing import List, Dict, Any
import asyncio

# Assuming these imports will be available from other modules
# from src.core.session_manager import SessionManager
# from src.language.entity_extractor_medical import MedicalEntityExtractor
# from src.core.memory_manager import MemoryManager
# from src.intelligence.llm_interface import LLMProvider # For token counting


class ContextBuilder:
    """
    Builds and manages conversation context for LLMs, ensuring that the most
    relevant and recent information is provided within token limits.
    """
    def __init__(self, session_manager_instance, entity_extractor_instance, memory_manager_instance, llm_provider_instance):
        """
        Initializes the ContextBuilder with its dependencies.
        
        :param session_manager_instance: An instance of SessionManager.
        :param entity_extractor_instance: An instance of MedicalEntityExtractor.
        :param memory_manager_instance: An instance of MemoryManager.
        :param llm_provider_instance: An instance of the LLMProvider (used for token counting).
        """
        self.session_manager = session_manager_instance
        self.entity_extractor = entity_extractor_instance
        self.memory_manager = memory_manager_instance
        self.llm = llm_provider_instance
        
        # Max tokens for the conversation history + prompt
        self.max_context_tokens = self.llm.config.get('max_context_tokens', 4000) 
        # A buffer to ensure the LLM has room for its response and the user's next prompt
        self.token_buffer = self.llm.config.get('token_buffer', 500)
        
        print("✅ ContextBuilder initialized.")

    async def _summarize_history(self, current_history: List[Dict], target_tokens: int) -> List[Dict]:
        """
        Summarizes the conversation history using the LLM to fit within token limits.
        Prioritizes recent messages if summarization is not possible or insufficient.
        """
        # Simple summarization: just keep the most recent N messages if too long.
        # A more advanced version would use the LLM to generate a summary.
        
        # Estimate tokens for current history
        full_history_text = "\n".join([msg['role'] + ": " + msg['text'] for msg in current_history])
        current_tokens = await self.llm.count_tokens(full_history_text)

        if current_tokens <= target_tokens:
            return current_history
        
        print(f"⚠️ History too long ({current_tokens} tokens). Summarizing to {target_tokens} tokens.")

        # Keep recent messages
        reduced_history = []
        tokens_so_far = 0
        
        # Iterate history in reverse to prioritize recent messages
        for msg in reversed(current_history):
            msg_text = msg['role'] + ": " + msg['text']
            msg_tokens = await self.llm.count_tokens(msg_text)
            
            if tokens_so_far + msg_tokens <= target_tokens:
                reduced_history.insert(0, msg) # Add to the beginning to maintain order
                tokens_so_far += msg_tokens
            else:
                break # Stop adding if next message exceeds limit
        
        # If we still have too many tokens (e.g., a single message is too long),
        # we would need to truncate that message or use LLM for summarization.
        # For now, we'll return the reduced history.
        
        # In a real system, you might invoke the LLM itself to generate a concise summary
        # of the oldest parts of the conversation if the token count is still too high.
        # Example: await self.llm.generate_summary(old_history_segment)
        
        print(f"History reduced to {len(reduced_history)} messages.")
        return reduced_history

    async def build_context(self, user_input: str, session_id: str) -> List[Dict]:
        """
        Builds the complete conversation context for the LLM.
        
        :param user_input: The current user's input.
        :param session_id: The ID of the current conversation session.
        :return: A list of message dictionaries suitable for an LLM (e.g., [{"role": "user", "text": "..."}]).
        """
        context_messages = []

        # 1. Get session history
        session = self.session_manager.get_session_by_uuid(session_id)
        if session:
            # Session history is typically stored as a list of {"role": "user/assistant", "text": "..."}
            full_history = session.history
        else:
            full_history = []
            
        # 2. Add relevant long-term memory chunks
        # This would typically involve a semantic search on the user's medical history
        # using the MedicalEntityExtractor and MemoryManager.
        extracted_entities = self.entity_extractor.extract(user_input)
        
        # For simplicity, let's assume we retrieve a fixed number of chunks
        relevant_memory_chunks = await self.memory_manager.retrieve_relevant_facts(
            user_id=session.user_id if session else None, # Assuming user_id in session
            query_text=user_input,
            entities=extracted_entities,
            limit=2
        )
        
        if relevant_memory_chunks:
            # Format memory chunks as system messages or prepend to history
            for chunk in relevant_memory_chunks:
                context_messages.append({"role": "system", "text": f"Relevant historical fact: {chunk}"})

        # 3. Combine current user input with history
        # (This is temporarily added to calculate token usage for summarization)
        temp_history_with_current = full_history + [{"role": "user", "text": user_input}]

        # 4. Summarize history if too long
        # Allocate tokens for current user_input and a potential LLM response
        remaining_tokens_for_history = self.max_context_tokens - await self.llm.count_tokens(user_input) - self.token_buffer
        
        summarized_history = await self._summarize_history(temp_history_with_current, remaining_tokens_for_history)
        
        # The final context for the LLM call will be `system_prompt` + `context_messages` + `summarized_history`
        # The system prompt is added by the ResponseGenerator.
        
        return context_messages + summarized_history

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockSession:
        def __init__(self, session_id, user_id):
            self.session_id = session_id
            self.user_id = user_id
            self.history = [
                {"role": "user", "text": "Hi, I have a medical question."}, 
                {"role": "assistant", "text": "Hello! What can I help you with?"},
                {"role": "user", "text": "I've had a headache for three days. It's quite severe."}, 
                {"role": "assistant", "text": "I see. Have you taken any medication for it?"},
                {"role": "user", "text": "Yes, I took Tylenol, but it didn't help much."}, 
                {"role": "assistant", "text": "Okay. Any other symptoms like fever or nausea?"},
                {"role": "user", "text": "No, just the headache."} 
            ]
    class MockSessionManager:
        def get_session_by_uuid(self, session_id):
            if session_id == "s1":
                return MockSession("s1", "user123")
            return None

    class MockEntityExtractor:
        def extract(self, text: str) -> List[Dict]:
            if "headache" in text:
                return [{"type": "SYMPTOM", "value": "headache"}]
            if "Tylenol" in text:
                return [{"type": "CHEMICAL", "value": "Tylenol"}]
            return []

    class MockMemoryManager:
        async def retrieve_relevant_facts(self, user_id: str, query_text: str, entities: List[Dict], limit: int) -> List[str]:
            if user_id == "user123" and "headache" in query_text:
                return ["User had a history of migraines last month."]
            return []

    class MockLLMProvider:
        def __init__(self, config):
            self.config = config
        async def count_tokens(self, text: str) -> int:
            return len(text.split()) # Simple word count as token estimate

    # --- Initialize ---
    mock_sm = MockSessionManager()
    mock_ee = MockEntityExtractor()
    mock_mm = MockMemoryManager()
    mock_llm = MockLLMProvider({"max_context_tokens": 100, "token_buffer": 10}) # Simulate small token limit

    builder = ContextBuilder(mock_sm, mock_ee, mock_mm, mock_llm)

    # --- Test ---
    print("--- Building context ---")
    user_input = "What should I do for this headache?"
    session_id = "s1"
    
    context = asyncio.run(builder.build_context(user_input, session_id))
    
    print("\n--- Generated Context ---")
    for msg in context:
        print(f"{msg['role'].upper()}: {msg['text']}")
    
    # Expected output:
    # 1. Relevant historical fact (if retrieved)
    # 2. Summarized session history
    # 3. Current user input
    print("\nContext build complete. History should be truncated/summarized to fit token limit.")
    
    total_tokens_in_context = asyncio.run(mock_llm.count_tokens("\n".join([msg['role'] + ": " + msg['text'] for msg in context])))
    print(f"Total tokens in final context messages: {total_tokens_in_context}")
    print(f"Max context tokens: {builder.max_context_tokens}, Token buffer: {builder.token_buffer}")
