import sys
import os
import logging
from typing import Dict, Type, Any, Optional

# Assuming BaseAgent is defined in src/agents/base_agent.py
from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Global registry for agent classes
_AGENT_REGISTRY: Dict[str, Type[BaseAgent]] = {}

# Simple pool for agent instances to reuse them
_AGENT_POOL: Dict[str, BaseAgent] = {}

def register_agent(name: str, agent_class: Type[BaseAgent]):
    """
    Registers an agent class with the factory.
    Args:
        name (str): The unique name/identifier for the agent type.
        agent_class (Type[BaseAgent]): The agent class to register.
    """
    if not issubclass(agent_class, BaseAgent):
        raise TypeError(f"Registered class '{agent_class.__name__}' must inherit from BaseAgent.")
    _AGENT_REGISTRY[name] = agent_class
    logger.info(f"Agent '{name}' registered with the factory.")

class AgentFactory:
    """
    A factory for creating and managing AI agent instances.
    Supports dynamic creation, context passing, and basic agent pooling.
    """

    @staticmethod
    def create_agent(name: str, context: Optional[Dict[str, Any]] = None, use_pooling: bool = True, **kwargs) -> BaseAgent:
        """
        Creates or retrieves an agent instance by name.
        Args:
            name (str): The name of the agent type to create.
            context (Optional[Dict[str, Any]]): Initial context to pass to the agent (e.g., session_id).
            use_pooling (bool): If True, attempts to reuse an existing agent from the pool.
            **kwargs: Additional arguments to pass to the agent's constructor.
        Returns:
            BaseAgent: An instance of the requested agent.
        Raises:
            ValueError: If the agent name is not registered.
        """
        agent_class = _AGENT_REGISTRY.get(name)
        if not agent_class:
            raise ValueError(f"Agent type '{name}' not registered. Available agents: {list(_AGENT_REGISTRY.keys())}")

        if use_pooling and name in _AGENT_POOL:
            agent = _AGENT_POOL[name]
            logger.debug(f"Reusing agent '{name}' from pool.")
            # Reset memory or update context for pooled agent
            agent.reset_memory() 
            if context:
                agent._memory.update(context) # Directly update internal memory if context is session-specific
            return agent
        
        # Create a new agent instance
        logger.info(f"Creating new agent instance for '{name}'.")
        
        # FIX: Explicitly pass the 'name' to the constructor so the agent knows its own registry identity.
        # This ensures agent.name matches the 'name' key used in the registry and pool.
        agent = agent_class(name=name, **kwargs)
        
        if context:
            agent._memory.update(context)
        
        if use_pooling:
            _AGENT_POOL[name] = agent # Add to pool for potential reuse
        return agent

    @staticmethod
    def release_agent(agent_instance: BaseAgent):
        """
        Releases an agent instance back to the pool or prepares it for cleanup.
        For simple pooling, this might just reset its state.
        Args:
            agent_instance (BaseAgent): The agent instance to release.
        """
        # Ensure we check the agent's actual name against the pool keys
        if agent_instance.name in _AGENT_POOL:
            agent_instance.reset_memory() # Clear sensitive session data
            logger.debug(f"Agent '{agent_instance.name}' released to pool and state reset.")
        else:
            logger.info(f"Agent '{agent_instance.name}' is not in the pool or was not pooled, preparing for cleanup.")
        # In a more complex scenario, this might involve explicit object destruction or resource release.

    @staticmethod
    def cleanup_all_agents():
        """
        Destroys all pooled agent instances.
        """
        for name, agent in list(_AGENT_POOL.items()): # Iterate over copy
            agent.reset_memory()
            # If agents hold significant resources, explicit shutdown might be needed
            del _AGENT_POOL[name]
            logger.info(f"Agent '{name}' removed from pool and cleaned up.")
        _AGENT_POOL.clear()
        logger.info("All agents in pool have been cleaned up.")

    @staticmethod
    def list_registered_agents() -> list[str]:
        """Returns a list of names of all registered agent types."""
        return list(_AGENT_REGISTRY.keys())

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Define some mock agent classes for testing
    class TriageAgent(BaseAgent):
        def __init__(self, name="triage"):
            super().__init__(name, "Handles initial patient triage.", {"role": "triage specialist"})
            self._memory["patient_symptoms"] = []
        async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
            self._memory["patient_symptoms"].append(text)
            return {"response_text": f"Triage agent received: {text}. What are your other symptoms?", "context_update": {}, "action": "ask_more"}
        def reset_memory(self):
            super().reset_memory()
            self._memory["patient_symptoms"] = []

    class AppointmentAgent(BaseAgent):
        def __init__(self, name="appointment"):
            super().__init__(name, "Manages appointment booking.", {"role": "receptionist"})
            self._memory["booking_slots"] = []
        async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
            return {"response_text": f"Appointment agent processing: {text}. What time works for you?", "context_update": {}, "action": "propose_slots"}
        def reset_memory(self):
            super().reset_memory()
            self._memory["booking_slots"] = []


    # Register the mock agents
    register_agent("triage", TriageAgent)
    register_agent("appointment", AppointmentAgent)

    print(f"\nRegistered agents: {AgentFactory.list_registered_agents()}")

    # Create a TriageAgent
    triage_agent_1 = AgentFactory.create_agent("triage", context={"session_id": "session1"})
    print(f"Agent 1 Name: {triage_agent_1.name}, Memory: {triage_agent_1.current_memory}")

    # Create another TriageAgent (should reuse from pool)
    triage_agent_2 = AgentFactory.create_agent("triage", context={"session_id": "session2"})
    print(f"Agent 2 Name: {triage_agent_2.name}, Memory: {triage_agent_2.current_memory}")
    assert triage_agent_1 is triage_agent_2 # Should be the same instance from pool

    # Create an AppointmentAgent (new instance)
    appointment_agent_1 = AgentFactory.create_agent("appointment", context={"session_id": "session3"})
    print(f"Agent 3 Name: {appointment_agent_1.name}, Memory: {appointment_agent_1.current_memory}")

    import asyncio
    asyncio.run(triage_agent_1.process_input("test", {}))

    # Release an agent
    AgentFactory.release_agent(triage_agent_1)
    print(f"Triage Agent 1 Memory after release: {triage_agent_1.current_memory}") # Should be reset

    # Cleanup all agents
    AgentFactory.cleanup_all_agents()
    print(f"Agent pool after cleanup: {_AGENT_POOL}")