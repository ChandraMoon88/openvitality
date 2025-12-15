import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import datetime
import asyncio
import re
import sys
import os
import random

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.agents.engagement.wellness_coach import WellnessCoachAgent

class TestWellnessCoachAgent(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        """Set up a fresh agent with mocked dependencies for each test."""
        # FIX: Use MagicMock for synchronous calls
        self.mock_nlu_engine = MagicMock()
        self.mock_habit_tracker_service = AsyncMock()
        
        self.agent = WellnessCoachAgent(
            nlu_engine=self.mock_nlu_engine,
            habit_tracker_service=self.mock_habit_tracker_service
        )
        # Mock the base agent's safety check to always pass
        self.agent._check_safety = AsyncMock(return_value=True)

        # Set default return values for NLU mock
        self.mock_nlu_engine.process_text.return_value = {"entities": [], "intent": {"name": "wellness_query"}}

    def test_initialization(self):
        """Test correct initialization of agent properties and memory."""
        self.assertEqual(self.agent.name, "WellnessCoachAgent")
        self.assertIn("wellness_goals", self.agent.current_memory)
        self.assertIn("tracked_habits", self.agent.current_memory)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")

    async def test_process_input_greeting_to_main_menu(self):
        """Test transition from greeting to main_menu."""
        response = await self.agent.process_input("Hi", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertIn("I'm your wellness coach.", response["response_text"])
        self.assertEqual(response["action"], "prompt_main_menu")

    async def test_process_input_main_menu_to_goal_setting(self):
        """Test transition to goal_setting from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Set a new goal.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "goal_setting")
        self.assertIn("What health goal are you aiming for today?", response["response_text"])
        self.assertEqual(response["action"], "ask_question")

    async def test_process_input_main_menu_to_habit_tracking(self):
        """Test transition to habit_tracking from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Track my habits.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "habit_tracking")
        self.assertIn("What habit would you like to log?", response["response_text"])
        self.assertEqual(response["action"], "prompt_habit_log")

    async def test_process_input_main_menu_to_health_tip(self):
        """Test transition to health_tip from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Give me health tips.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu") # Should return to main_menu
        self.assertIn("Here's a health tip for you:", response["response_text"])
        self.assertEqual(response["action"], "provide_tip")

    async def test_process_input_main_menu_to_review_progress(self):
        """Test transition to review_progress from main_menu."""
        self.agent._memory["conversation_stage"] = "main_menu"
        
        # FIX: Populate memory so the "overview" message is triggered instead of "no goals" message
        self.agent._memory["wellness_goals"] = {
            "drink water": {"target": "8 glasses", "time_frame": "daily"}
        }
        
        response = await self.agent.process_input("My progress.", {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu") 
        self.assertIn("Here's an overview of your wellness journey:", response["response_text"])
        self.assertEqual(response["action"], "show_progress")

    async def test_process_input_unrecognized(self):
        """Test handling of unrecognized input."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = await self.agent.process_input("Blah blah blah.", {})
        self.assertIn("I didn't quite catch that.", response["response_text"])
        self.assertEqual(response["action"], "clarify_wellness")

    def test_ask_next_goal_question(self):
        """Test that _ask_next_goal_question returns correct questions."""
        self.agent._memory["conversation_stage"] = "goal_setting"
        self.agent._memory["current_question_index"] = 0
        response = self.agent._ask_next_goal_question()
        self.assertEqual(response["response_text"], self.agent.goal_setting_questions[0])
        self.assertEqual(self.agent.current_memory["current_question_index"], 1)

    async def test_process_goal_answer_full_flow(self):
        """Test full goal setting flow."""
        self.agent._memory["conversation_stage"] = "goal_setting"
        # FIX: Set index to 1, implying Q0 was already asked and we are answering it
        self.agent._memory["current_question_index"] = 1
        self.agent._memory["current_goal_info"] = {}

        # 1st answer (goal idea) - maps to index 0
        # process_input calls _process_goal_answer which increments index to 2 and returns next Q
        await self.agent.process_input("drink more water", {})
        self.assertEqual(self.agent.current_memory["current_goal_info"]["goal_idea"], "drink more water")
        self.assertEqual(self.agent.current_memory["current_question_index"], 2)

        # 2nd answer (SMART target) - maps to index 1
        await self.agent.process_input("8 glasses daily", {})
        self.assertEqual(self.agent.current_memory["current_goal_info"]["smart_target"], "8 glasses daily")
        self.assertEqual(self.agent.current_memory["current_question_index"], 3)

        # 3rd answer (Time-bound) - maps to index 2
        response = await self.agent.process_input("for 30 days", {})
        self.assertIn("Fantastic! We've set your goal", response["response_text"])
        self.assertIn("drink more water", self.agent.current_memory["wellness_goals"])
        self.assertEqual(self.agent.current_memory["wellness_goals"]["drink more water"]["target"], "8 glasses daily")
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")
        self.assertNotIn("current_goal_info", self.agent.current_memory) 

    async def test_log_habit_activity_water(self):
        """Test logging water intake."""
        self.agent._memory["conversation_stage"] = "habit_tracking"
        response = await self.agent.process_input("I drank 8 glasses of water.", {"user_id": "test_user"})
        self.assertIn("Great job logging your water intake!", response["response_text"])
        self.assertIn("water_intake", self.agent.current_memory["tracked_habits"])
        self.assertEqual(self.agent.current_memory["tracked_habits"]["water_intake"]["total_count"], 8.0)
        self.mock_habit_tracker_service.log_activity.assert_called_once()
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")

    async def test_log_habit_activity_steps(self):
        """Test logging steps walked."""
        self.agent._memory["conversation_stage"] = "habit_tracking"
        response = await self.agent.process_input("I walked 10000 steps.", {"user_id": "test_user"})
        self.assertIn("Great job logging your steps walked!", response["response_text"])
        self.assertIn("steps_walked", self.agent.current_memory["tracked_habits"])
        self.assertEqual(self.agent.current_memory["tracked_habits"]["steps_walked"]["total_count"], 10000.0)

    async def test_log_habit_activity_sleep(self):
        """Test logging sleep duration."""
        self.agent._memory["conversation_stage"] = "habit_tracking"
        response = await self.agent.process_input("I slept 7 hours.", {"user_id": "test_user"})
        self.assertIn("Great job logging your sleep duration!", response["response_text"])
        self.assertIn("sleep_duration", self.agent.current_memory["tracked_habits"])
        self.assertEqual(self.agent.current_memory["tracked_habits"]["sleep_duration"]["total_count"], 7.0)

    async def test_log_habit_activity_unrecognized(self):
        """Test logging an unrecognized habit activity."""
        self.agent._memory["conversation_stage"] = "habit_tracking"
        response = await self.agent.process_input("I read a book.", {"user_id": "test_user"})
        self.assertIn("I'm not sure which habit you're trying to log.", response["response_text"])
        self.assertEqual(response["action"], "clarify_habit")
        self.mock_habit_tracker_service.log_activity.assert_not_called()

    def test_update_habit_streak_new_streak(self):
        """Test starting a new habit streak."""
        today = datetime.date.today()
        response_text = self.agent._update_habit_streak("test_habit", {"value": 1, "unit": "count"})
        self.assertIn("started a new streak for test habit!", response_text)
        self.assertEqual(self.agent.current_memory["tracked_habits"]["test_habit"]["streak"], 1)
        self.assertEqual(self.agent.current_memory["tracked_habits"]["test_habit"]["last_logged_date"], today)

    def test_update_habit_streak_continue_streak(self):
        """Test continuing an existing habit streak."""
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        self.agent._memory["tracked_habits"]["test_habit"] = {
            "last_logged_date": yesterday, "streak": 5, "total_count": 5, "log_history": []
        }
        response_text = self.agent._update_habit_streak("test_habit", {"value": 1, "unit": "count"})
        self.assertIn("Amazing! You're on a 6-day streak for test habit!", response_text)
        self.assertEqual(self.agent.current_memory["tracked_habits"]["test_habit"]["streak"], 6)
        self.assertEqual(self.agent.current_memory["tracked_habits"]["test_habit"]["last_logged_date"], today)

    def test_update_habit_streak_already_logged_today(self):
        """Test logging a habit already logged today."""
        today = datetime.date.today()
        self.agent._memory["tracked_habits"]["test_habit"] = {
            "last_logged_date": today, "streak": 1, "total_count": 1, "log_history": []
        }
        response_text = self.agent._update_habit_streak("test_habit", {"value": 1, "unit": "count"})
        self.assertIn("You've already logged your test habit for today!", response_text)
        self.assertEqual(self.agent.current_memory["tracked_habits"]["test_habit"]["streak"], 1)

    def test_provide_health_tip(self):
        """Test that a random health tip is provided."""
        response = self.agent._provide_health_tip()
        self.assertIn("Here's a health tip for you:", response["response_text"])
        self.assertIn(response["response_text"].split(": ")[1], self.agent.health_tips)
        self.assertEqual(self.agent.current_memory["conversation_stage"], "main_menu")

    def test_review_progress_no_goals_or_habits(self):
        """Test progress review when no goals or habits are set."""
        self.agent._memory["conversation_stage"] = "main_menu"
        response = self.agent._review_progress()
        self.assertIn("You haven't set any goals or tracked any habits yet.", response["response_text"])
        self.assertEqual(response["action"], "offer_goal_setting")

    def test_review_progress_with_goals_and_habits(self):
        """Test progress review with existing goals and habits."""
        self.agent._memory["wellness_goals"] = {
            "drink more water": {"target": "8 glasses", "time_frame": "30 days", "progress": 0, "start_date": datetime.date.today(), "last_update": datetime.date.today()}
        }
        self.agent._memory["tracked_habits"] = {
            "steps_walked": {"last_logged_date": datetime.date.today(), "streak": 5, "total_count": 50000, "log_history": []}
        }
        self.agent._memory["conversation_stage"] = "main_menu"
        response = self.agent._review_progress()
        self.assertIn("--- Your Goals ---", response["response_text"])
        self.assertIn("--- Your Habits ---", response["response_text"])
        self.assertIn("8 glasses", response["response_text"])
        self.assertIn("Current streak: 5 days.", response["response_text"])

    def test_reset_memory(self):
        """Test that the agent's memory is properly reset."""
        self.agent._memory["wellness_goals"]["test"] = {"target": "target"}
        self.agent._memory["tracked_habits"]["test"] = {"streak": 1}
        self.agent._memory["conversation_stage"] = "habit_tracking"
        self.agent._memory["current_goal_info"] = {"some_info": "value"} # Ensure this is also cleared
        
        self.agent.reset_memory()
        
        self.assertEqual(self.agent.current_memory["wellness_goals"], {})
        self.assertEqual(self.agent.current_memory["tracked_habits"], {})
        self.assertEqual(self.agent.current_memory["conversation_stage"], "greeting")
        self.assertNotIn("current_goal_info", self.agent.current_memory)


if __name__ == '__main__':
    unittest.main()