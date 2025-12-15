# src/core/context_router.py
"""
The "traffic cop" that routes incoming messages to the correct agent.

This router uses intent, conversation history, and agent availability to make
intelligent routing decisions, ensuring a smooth and logical conversation flow.
"""
from typing import Dict, Any

# Placeholder imports
# from . import logger
# from .session_manager import Session
# from .agents.base import BaseAgent
# from .agents.emergency import EmergencyAgent

class ContextRouter:
    def __init__(self, agent_registry: Dict[str, Any]):
        """
        Initializes the ContextRouter.

        Args:
            agent_registry: A dictionary mapping intent names to agent instances.
        """
        self.agent_registry = agent_registry
        # self.emergency_agent = EmergencyAgent()
        # logger.info("ContextRouter initialized.")
        print("ContextRouter initialized.")

    def get_agent(self, session: Dict[str, Any], intent: str, confidence: float) -> Any:
        """
        Determines the appropriate agent for a request based on various factors.

        Args:
            session: The user's current session object.
            intent: The classified intent of the user's message.
            confidence: The confidence score of the intent classification.

        Returns:
            An instance of the selected agent.
        """
        current_agent_name = session.get("context", {}).get("current_agent")
        
        # 1. Priority Override: Emergency always takes precedence.
        if intent == "medical_emergency":
            # logger.warning(f"Emergency detected! Routing to EmergencyAgent. Session: {session['session_id']}")
            # return self.emergency_agent
            print("Emergency detected, routing to emergency agent.")
            return self.agent_registry.get(intent)


        # 2. Sticky Routing: If the user is in the middle of a conversation, keep them with the same agent.
        # This prevents the AI from getting confused if the user's phrasing changes slightly.
        # An explicit intent change (e.g., from "symptom_report" to "appointment_booking") breaks the stickiness.
        is_intent_changed = intent != session.get("context", {}).get("last_intent")
        
        if current_agent_name and not is_intent_changed:
            agent = self.agent_registry.get(current_agent_name)
            if agent and agent.is_available():
                # logger.debug(f"Sticky routing to {current_agent_name} for session {session['session_id']}")
                return agent

        # 3. Intent-based Routing: If no sticky route, map the new intent to an agent.
        if confidence > 0.7: # Confidence threshold
            agent = self.agent_registry.get(intent)
            if agent and agent.is_available():
                # logger.info(f"Routing to new agent {intent} for session {session['session_id']}")
                return agent
        
        # 4. Fallback: If no specific agent is found or confidence is low, use a default agent.
        # logger.debug(f"No specific agent found for intent '{intent}'. Using fallback agent.")
        return self.agent_registry.get("general_question")

# Example of a base agent class structure (would be in agents/base.py)
# class BaseAgent:
#     def is_available(self) -> bool:
#         # In a real system, this would check load, dependencies, etc.
#         return True
