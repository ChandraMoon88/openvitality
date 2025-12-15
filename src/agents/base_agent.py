import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Abstract Base Class (ABC) for all AI agents in the OpenVitality system.
    Defines the core interface and common attributes for agent behavior,
    including input processing, state management, memory, safety hooks, and persona.
    """

    def __init__(self, name: str, description: str, persona: Dict[str, Any], tools: Optional[List[Any]] = None):
        """
        Initializes the BaseAgent with fundamental properties.

        Args:
            name (str): The unique name of the agent (e.g., "TriageAgent", "GP_Agent").
            description (str): A brief description of the agent's purpose.
            persona (Dict[str, Any]): A dictionary defining the agent's personality,
                                      directives, and communication style. This often
                                      translates into the system prompt for an LLM.
            tools (Optional[List[Any]]): A list of external functions or APIs this agent can call.
        """
        self.name = name
        self.description = description
        self._persona = persona 
        self.tools = tools if tools is not None else []
        self._memory: Dict[str, Any] = {} # Short-term context for the current session
        
        logger.info(f"BaseAgent '{self.name}' initialized.")

    @abstractmethod
    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input and generates a response. This is the core logic
        that every concrete agent must implement.

        Args:
            text (str): The user's input text.
            context (Dict[str, Any]): A dictionary containing relevant session context
                                       (e.g., call_id, user_profile, NLU_output).

        Returns:
            Dict[str, Any]: A dictionary containing the agent's response,
                            potentially updated context, and any actions to take.
                            Example: {"response_text": "...", "context_update": {...}, "action": "..."}
        """
        pass

    def get_state(self) -> Dict[str, Any]:
        """
        Returns the current state of the agent for the ongoing session.
        This includes the agent's memory and current persona.
        """
        return {
            "agent_name": self.name,
            "description": self.description,
            "persona": self._persona.copy(), 
            "memory": self._memory.copy()
        }

    def reset_memory(self):
        """
        Clears the short-term memory of the agent for the current session.
        """
        self._memory = {}
        logger.debug(f"Memory reset for agent '{self.name}'.")

    def set_persona(self, new_persona: Dict[str, Any]):
        """
        Updates the agent's persona. This can be used to adapt the agent's
        behavior or communication style dynamically.
        """
        self._persona = new_persona
        logger.info(f"Persona updated for agent '{self.name}'.")

    async def _check_safety(self, input_text: str, response_text: Optional[str] = None) -> bool:
        """
        A safety hook that runs before generating a response and/or before
        sending it to the user. All agents must implicitly pass this check.
        
        Args:
            input_text (str): The user's original input.
            response_text (Optional[str]): The agent's generated response (if available).

        Returns:
            bool: True if the input/response passes safety checks, False otherwise.
        """
        logger.debug(f"Running safety checks for agent '{self.name}'...")
        # Placeholder for actual safety module integration (e.g., safety_monitor)
        # if SafetyMonitor.is_unsafe(input_text, response_text):
        #     logger.warning(f"Safety check failed for agent '{self.name}'.")
        #     return False
        return True # Assume safe for now

    async def execute_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Executes a registered tool/function. Handles both sync and async tools.
        """
        for tool in self.tools:
            if hasattr(tool, 'name') and tool.name == tool_name:
                logger.info(f"Agent '{self.name}' executing tool '{tool_name}' with args: {kwargs}")
                
                # Execute the tool. If it's async, this returns a coroutine object.
                # If it's sync, this returns the actual result.
                result = tool.execute(**kwargs)

                # Check if the result is a coroutine (awaitable)
                if asyncio.iscoroutine(result):
                    return await result
                
                return result

        raise ValueError(f"Tool '{tool_name}' not found for agent '{self.name}'.")

    @property
    def current_persona(self) -> Dict[str, Any]:
        """Read-only access to the agent's current persona."""
        return self._persona.copy()
    
    @property
    def current_memory(self) -> Dict[str, Any]:
        """Read-only access to the agent's current memory."""
        return self._memory.copy()

# Example of a concrete agent implementation
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockTool:
        def __init__(self, name: str):
            self.name = name
        async def execute(self, query: str) -> str:
            logger.info(f"MockTool '{self.name}' executed with query: '{query}'")
            return f"Result from {self.name} for '{query}'"

    class SimpleChatAgent(BaseAgent):
        def __init__(self):
            super().__init__(
                name="SimpleChatAgent",
                description="A basic conversational agent for general queries.",
                persona={
                    "role": "friendly assistant",
                    "directives": ["be helpful", "answer questions directly"],
                    "style": "informal"
                },
                tools=[MockTool("web_search")]
            )
            self._memory["conversation_history"] = []

        async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
            logger.info(f"SimpleChatAgent processing input: '{text}' with context: {context}")
            
            # Simulate safety check
            if not await self._check_safety(text):
                return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}}

            self._memory["conversation_history"].append({"user": text})

            response_text = f"You said: '{text}'. "
            if "search" in text.lower():
                tool_result = await self.execute_tool("web_search", query=text)
                response_text += tool_result
            else:
                response_text += "How can I help you further?"

            self._memory["conversation_history"].append({"agent": response_text})
            
            return {
                "response_text": response_text,
                "context_update": {"last_agent_response": response_text},
                "action": "respond"
            }

    async def run_example_agent():
        agent = SimpleChatAgent()
        context = {"user_id": "test_user_123", "session_id": "session_abc"}

        print("\n--- First Interaction ---")
        response1 = await agent.process_input("Hello, tell me about the weather.", context)
        print(f"Agent Response: {response1['response_text']}")
        print(f"Agent Memory: {agent.current_memory}")

        print("\n--- Second Interaction (using tool) ---")
        response2 = await agent.process_input("Can you search for the capital of France?", context)
        print(f"Agent Response: {response2['response_text']}")
        print(f"Agent Memory: {agent.current_memory}")

        print("\n--- Reset Memory ---")
        agent.reset_memory()
        print(f"Agent Memory after reset: {agent.current_memory}")

        print("\n--- Change Persona ---")
        agent.set_persona({"role": "formal assistant", "directives": ["be precise"], "style": "formal"})
        print(f"Agent Persona: {agent.current_persona}")

    asyncio.run(run_example_agent())