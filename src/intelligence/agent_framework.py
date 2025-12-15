# src/intelligence/agent_framework.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Type, List
import asyncio

# This dictionary will store a mapping of agent names to their respective classes.
_agent_registry: Dict[str, Type["AIAgent"]] = {}

def register_agent(name: str):
    """
    A decorator to register an AIAgent class with the framework.
    
    Example:
    @register_agent("medical_triage")
    class MedicalTriageAgent(AIAgent):
        # ... implementation ...
    """
    def decorator(cls: Type["AIAgent"]) -> Type["AIAgent"]:
        if not issubclass(cls, AIAAgent):
            raise TypeError(f"Class {cls.__name__} must inherit from AIAgent.")
        _agent_registry[name] = cls
        return cls
    return decorator

class AIAgent(ABC):
    """
    Abstract Base Class for all AI agents.
    
    Each agent is responsible for a specific domain or task within the AI system.
    """
    def __init__(self, config: Dict[str, Any], tools: Dict[str, Any]):
        """
        Initializes the agent.
        
        :param config: The application configuration.
        :param tools: A dictionary of callable tools/functions the agent can use.
        """
        self.config = config
        self.tools = tools
        self.agent_name = self.__class__.__name__

    @abstractmethod
    async def can_handle(self, context: Dict[str, Any]) -> bool:
        """
        Determines if this agent is capable of handling the current user request
        based on the provided context.
        
        :param context: The aggregated conversation context (user input, session state, etc.).
        :return: True if the agent can handle the request, False otherwise.
        """
        pass

    @abstractmethod
    async def handle_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the user request and generates a response.
        
        :param context: The aggregated conversation context.
        :return: A dictionary containing the agent's response, status, and any data
                 to be stored in the session.
        """
        pass

class AgentFramework:
    """
    Manages and orchestrates multiple AI agents.
    """
    def __init__(self, config: Dict[str, Any], all_tools: Dict[str, Any]):
        self.config = config
        self.all_tools = all_tools
        self.agents: List[AIAgent] = []
        self._load_agents()
        print("✅ AgentFramework initialized and agents loaded.")

    def _load_agents(self):
        """
        Dynamically loads and initializes all registered agents.
        """
        for name, agent_cls in _agent_registry.items():
            try:
                # Agents might only need a subset of all_tools, or specific ones
                # For simplicity, passing all_tools for now.
                agent_instance = agent_cls(self.config, self.all_tools)
                self.agents.append(agent_instance)
                print(f"Loaded agent: {name}")
            except Exception as e:
                print(f"🚨 Failed to load agent '{name}': {e}")
        
        # Sort agents if there's a priority mechanism, e.g., emergency agents first
        # For now, just keep the order of registration.

    async def route_and_handle(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Routes the user's message to the most appropriate agent and gets a response.
        
        :param context: The aggregated conversation context.
        :return: The response from the selected agent, or a fallback if no agent handles it.
        """
        for agent in self.agents:
            if await agent.can_handle(context):
                print(f"➡️ Routing message to {agent.agent_name}")
                return await agent.handle_message(context)
        
        # Fallback if no agent can handle the request
        print("🤷 No specific agent found to handle the request. Using fallback.")
        return {"response_text": "I'm not sure how to help with that. Can you rephrase?", "status": "unhandled"}

# --- Example Tools (Mock) ---
class MockAPIManager:
    async def call_external_api(self, service, data):
        print(f"MockAPIManager: Calling {service} with {data}")
        return {"result": "success"}

class MockDatabase:
    async def get_patient_data(self, patient_id):
        print(f"MockDatabase: Fetching data for {patient_id}")
        return {"name": "John Doe", "condition": "fever"}

# --- Example Agents ---
@register_agent("medical_triage")
class MedicalTriageAgent(AIAgent):
    async def can_handle(self, context: Dict[str, Any]) -> bool:
        # This agent handles symptom reports or medical questions
        user_input_lower = context.get("user_input", "").lower()
        intent = context.get("intent", {}).get("primary_intent")
        
        if intent == "symptom_report" or "symptom" in user_input_lower or "medical question" in user_input_lower:
            return True
        return False

    async def handle_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        patient_name = context.get("session_context", {}).get("patient_name", "patient")
        current_symptoms = [e['value'] for e in context.get("entities", []) if e['type'] == 'SYMPTOM']
        
        response = f"Okay {patient_name}, you've mentioned {', '.join(current_symptoms) if current_symptoms else 'some symptoms'}. Let me ask you a few more questions to understand your condition better."
        
        # Example of using a tool
        db_data = await self.tools["database"].get_patient_data(context.get("session_context", {}).get("user_id"))
        response += f" I see from your records that you previously had {db_data.get('condition')}."

        return {"response_text": response, "status": "in_triage"}

@register_agent("appointment_booking")
class AppointmentBookingAgent(AIAgent):
    async def can_handle(self, context: Dict[str, Any]) -> bool:
        intent = context.get("intent", {}).get("primary_intent")
        if intent == "appointment_booking":
            return True
        return False

    async def handle_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        response = "Certainly, I can help you book an appointment. What day and time are you looking for?"
        # Example of using a tool
        await self.tools["api_manager"].call_external_api("calendar_service", {"action": "check_availability"})
        return {"response_text": response, "status": "booking_in_progress"}

@register_agent("small_talk")
class SmallTalkAgent(AIAgent):
    async def can_handle(self, context: Dict[str, Any]) -> bool:
        intent = context.get("intent", {}).get("primary_intent")
        if intent == "small_talk":
            return True
        return False
    
    async def handle_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        user_input_lower = context.get("user_input", "").lower()
        if "hello" in user_input_lower or "hi" in user_input_lower:
            return {"response_text": "Hello there! How can I help you today?", "status": "small_talk_done"}
        if "thank you" in user_input_lower or "thanks" in user_input_lower:
            return {"response_text": "You're most welcome!", "status": "small_talk_done"}
        return {"response_text": "That's nice to hear!", "status": "small_talk_done"}


# Example Usage
if __name__ == "__main__":
    mock_config = {}
    mock_tools = {
        "api_manager": MockAPIManager(),
        "database": MockDatabase()
    }
    
    framework = AgentFramework(mock_config, mock_tools)

    # --- Simulate context for routing ---
    # Context should be built by ContextBuilder (File 89)
    context_symptom = {
        "user_input": "I have a terrible headache.",
        "intent": {"primary_intent": "symptom_report"},
        "entities": [{"type": "SYMPTOM", "value": "headache"}],
        "session_context": {"session_id": "test_s1", "user_id": "user123", "patient_name": "Jane"}
    }
    
    context_booking = {
        "user_input": "I need to book an appointment.",
        "intent": {"primary_intent": "appointment_booking"},
        "entities": [],
        "session_context": {"session_id": "test_s2", "user_id": "user123", "patient_name": "Jane"}
    }
    
    context_smalltalk = {
        "user_input": "Hello",
        "intent": {"primary_intent": "small_talk"},
        "entities": [],
        "session_context": {"session_id": "test_s3", "user_id": "user123"}
    }

    context_unhandled = {
        "user_input": "What is the meaning of life?",
        "intent": {"primary_intent": "general_question"},
        "entities": [],
        "session_context": {"session_id": "test_s4", "user_id": "user123"}
    }

    print("\n--- Routing symptom report ---")
    response_symptom = asyncio.run(framework.route_and_handle(context_symptom))
    print(f"Agent Response: {response_symptom}")

    print("\n--- Routing appointment booking ---")
    response_booking = asyncio.run(framework.route_and_handle(context_booking))
    print(f"Agent Response: {response_booking}")

    print("\n--- Routing small talk ---")
    response_smalltalk = asyncio.run(framework.route_and_handle(context_smalltalk))
    print(f"Agent Response: {response_smalltalk}")
    
    print("\n--- Routing unhandled query ---")
    response_unhandled = asyncio.run(framework.route_and_handle(context_unhandled))
    print(f"Agent Response: {response_unhandled}")
