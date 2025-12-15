import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from abc import ABC, abstractmethod

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
 
from src.agents.base_agent import BaseAgent

# Concrete implementation for testing abstract methods
class ConcreteAgent(BaseAgent):
    def __init__(self, name="TestAgent", description="A test agent", persona=None, tools=None):
        # Fix: Use None as default to avoid mutable default argument pollution across tests
        if persona is None:
            persona = {"role": "tester"}
        
        super().__init__(name, description, persona, tools)
        self._memory["test_data"] = "initial"

    async def process_input(self, text: str, context: dict) -> dict:
        self._memory["last_input"] = text
        return {"response_text": f"Processed: {text}", "context_update": {}, "action": "respond"}

class TestBaseAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.agent = ConcreteAgent()

    def test_initialization(self):
        """Test correct assignment of properties during initialization."""
        self.assertEqual(self.agent.name, "TestAgent")
        self.assertEqual(self.agent.description, "A test agent")
        self.assertEqual(self.agent.current_persona, {"role": "tester"})
        self.assertEqual(self.agent.tools, [])
        self.assertEqual(self.agent.current_memory, {"test_data": "initial"})

        # Test with tools
        mock_tool = MagicMock()
        agent_with_tools = ConcreteAgent(name="ToolAgent", tools=[mock_tool])
        self.assertEqual(agent_with_tools.tools, [mock_tool])

    def test_abstract_method_enforcement(self):
        """Test that BaseAgent cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            # Attempting to instantiate BaseAgent directly should raise TypeError
            BaseAgent(name="Abstract", description="Desc", persona={})

    async def test_process_input_implementation(self):
        """Test that the concrete implementation of process_input works."""
        response = await self.agent.process_input("hello", {})
        self.assertEqual(response["response_text"], "Processed: hello")
        self.assertEqual(self.agent.current_memory["last_input"], "hello")

    def test_get_state(self):
        """Test that get_state returns correct agent state and a copy of memory."""
        state = self.agent.get_state()
        self.assertEqual(state["agent_name"], "TestAgent")
        self.assertEqual(state["description"], "A test agent")
        self.assertEqual(state["persona"], {"role": "tester"})
        
        # Test that memory is a copy
        self.assertDictEqual(state["memory"], {"test_data": "initial"})
        self.assertIsNot(state["memory"], self.agent._memory)

    def test_reset_memory(self):
        """Test that reset_memory clears the agent's memory."""
        self.agent._memory["new_data"] = "some_value"
        self.agent.reset_memory()
        self.assertEqual(self.agent.current_memory, {})

    def test_set_persona(self):
        """Test that set_persona correctly updates the agent's persona."""
        new_persona = {"role": "new_role", "style": "new_style"}
        self.agent.set_persona(new_persona)
        self.assertEqual(self.agent.current_persona, new_persona)

    async def test_check_safety(self):
        """Test that _check_safety returns True by default."""
        self.assertTrue(await self.agent._check_safety("user input"))
        self.assertTrue(await self.agent._check_safety("user input", "agent response"))

    async def test_execute_tool_success_sync(self):
        """Test successful execution of a synchronous tool."""
        mock_tool = MagicMock(name="SyncTool")
        mock_tool.name = "SyncTool"
        mock_tool.execute.return_value = "sync_result"
        agent = ConcreteAgent(tools=[mock_tool])

        result = await agent.execute_tool("SyncTool", param="value")
        self.assertEqual(result, "sync_result")
        mock_tool.execute.assert_called_once_with(param="value")

    async def test_execute_tool_success_async(self):
        """Test successful execution of an asynchronous tool using AsyncMock."""
        mock_tool = MagicMock(name="AsyncTaskTool")
        mock_tool.name = "AsyncTaskTool"
        
        # Use AsyncMock, which returns a coroutine when called
        mock_tool.execute = AsyncMock(return_value="async_result")
        
        agent = ConcreteAgent(tools=[mock_tool])

        result = await agent.execute_tool("AsyncTaskTool", param="value_async")
        self.assertEqual(result, "async_result")
        mock_tool.execute.assert_called_once_with(param="value_async")

    async def test_execute_tool_not_found(self):
        """Test that calling a non-existent tool raises a ValueError."""
        with self.assertRaisesRegex(ValueError, "Tool 'NonExistentTool' not found"):
            await self.agent.execute_tool("NonExistentTool")

    def test_current_persona_property(self):
        """Test that current_persona property returns the correct persona."""
        self.assertEqual(self.agent.current_persona, {"role": "tester"})
        # Ensure it's read-only in terms of internal modification
        self.agent.current_persona["new_key"] = "new_value"
        self.assertNotIn("new_key", self.agent._persona)

    def test_current_memory_property(self):
        """Test that current_memory property returns a copy of memory."""
        self.assertEqual(self.agent.current_memory, {"test_data": "initial"})
        self.assertIsNot(self.agent.current_memory, self.agent._memory)
        # Ensure it's read-only in terms of internal modification
        self.agent.current_memory["new_key"] = "new_value"
        self.assertNotIn("new_key", self.agent._memory)


if __name__ == '__main__':
    unittest.main()