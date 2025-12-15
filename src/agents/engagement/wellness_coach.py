import logging
import datetime
from typing import Dict, Any, List, Optional
import asyncio
import random
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class WellnessCoachAgent(BaseAgent):
    """
    A specialized AI agent acting as a wellness coach, focused on health motivation.
    It assists users with goal setting, habit tracking, and provides motivational
    and educational content to encourage healthy lifestyles.
    """
    def __init__(self, nlu_engine: Any = None, habit_tracker_service: Any = None):
        super().__init__(
            name="WellnessCoachAgent",
            description="Motivates users towards healthier habits and wellness goals.",
            persona={
                "role": "energetic, encouraging, and non-judgmental wellness coach",
                "directives": [
                    "Help users set SMART (Specific, Measurable, Achievable, Relevant, Time-bound) goals.",
                    "Use motivational interviewing techniques to encourage self-efficacy.",
                    "Facilitate tracking of key health habits (e.g., water, steps, sleep).",
                    "Provide positive reinforcement and celebrate progress.",
                    "Offer educational content and daily health tips.",
                    "Never give medical advice; always defer to healthcare professionals for health conditions."
                ],
                "style": "positive, inspiring, supportive, friendly"
            }
        )
        self.nlu_engine = nlu_engine
        self.habit_tracker_service = habit_tracker_service
        
        self._memory["wellness_goals"] = {} # {goal_name: {type, target, progress, start_date, last_update}}
        self._memory["tracked_habits"] = {} # {habit_name: {last_logged_date, streak, total_count}}
        self._memory["conversation_stage"] = "greeting" # greeting, goal_setting, habit_tracking, coaching, tips
        self._memory["current_question_index"] = 0

        self.goal_setting_questions = [
            "What health goal are you aiming for today? (e.g., 'drink more water', 'walk more', 'get better sleep')",
            "How can we make this goal specific and measurable? For example, 'drink 8 glasses of water daily' or 'walk 10,000 steps daily'.",
            "By when would you like to achieve this goal, or for how long would you like to maintain this habit?"
        ]

        self.health_tips = [
            "Remember to stay hydrated throughout the day!",
            "Even a short walk can boost your mood and energy.",
            "Prioritize 7-9 hours of quality sleep each night for better health.",
            "Try incorporating more fruits and vegetables into your meals.",
            "Take a few minutes to practice mindfulness or deep breathing when you feel stressed."
        ]
        logger.info("WellnessCoachAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input for wellness coaching.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "main_menu"
            return {
                "response_text": "Hi there! I'm your wellness coach. What health goals or habits are you focusing on today?",
                "context_update": {"wellness_stage": "main_menu"},
                "action": "prompt_main_menu"
            }
        
        elif self._memory["conversation_stage"] == "main_menu":
            if "set a goal" in text_lower or "new goal" in text_lower:
                self._memory["conversation_stage"] = "goal_setting"
                self._memory["current_question_index"] = 0
                self._memory["current_goal_info"] = {}
                return self._ask_next_goal_question()
            elif "track my habits" in text_lower or "log activity" in text_lower:
                self._memory["conversation_stage"] = "habit_tracking"
                return {"response_text": "Great! What habit would you like to log? (e.g., 'I drank 8 glasses of water', 'I walked 5000 steps')", "context_update": {"wellness_stage": "log_habit"}, "action": "prompt_habit_log"}
            elif "health tips" in text_lower or "advice" in text_lower:
                return self._provide_health_tip()
            elif "my progress" in text_lower or "my goals" in text_lower:
                return self._review_progress()
        
        elif self._memory["conversation_stage"] == "goal_setting":
            return self._process_goal_answer(text, nlu_output, context)
        
        elif self._memory["conversation_stage"] == "habit_tracking":
            return await self._log_habit_activity(text_lower, nlu_output, context)
            
        return {"response_text": "I didn't quite catch that. Could you tell me if you want to set a goal, track a habit, or get a health tip?", "context_update": {}, "action": "clarify_wellness"}

    def _ask_next_goal_question(self) -> Dict[str, Any]:
        """Returns the next question in the goal-setting flow."""
        question_text = self.goal_setting_questions[self._memory["current_question_index"]]
        self._memory["current_question_index"] += 1
        return {
            "response_text": question_text,
            "context_update": {"wellness_stage": "goal_setting", "question_asked": question_text},
            "action": "ask_question"
        }

    def _process_goal_answer(self, text: str, nlu_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes answers to goal-setting questions and helps define a SMART goal.
        """
        # Determine question index (subtract 1 because _ask_next_goal_question increments it beforehand)
        answered_index = self._memory["current_question_index"] - 1
        current_goal_info = self._memory["current_goal_info"]

        if answered_index == 0: # Initial goal idea
            current_goal_info["goal_idea"] = text
        elif answered_index == 1: # Specific and Measurable
            current_goal_info["smart_target"] = text
        elif answered_index == 2: # Time-bound
            current_goal_info["time_frame"] = text
            return self._finalize_goal(current_goal_info)
        
        self._memory["current_goal_info"] = current_goal_info
        return self._ask_next_goal_question()

    def _finalize_goal(self, current_goal_info: Dict[str, Any]) -> Dict[str, Any]:
        """Finalizes the goal creation process."""
        goal_name = current_goal_info.get("goal_idea", "new goal")
        self._memory["wellness_goals"][goal_name] = {
            "type": current_goal_info.get("goal_idea"),
            "target": current_goal_info.get("smart_target"),
            "time_frame": current_goal_info.get("time_frame"),
            "progress": 0,
            "start_date": datetime.date.today(),
            "last_update": datetime.date.today()
        }
        
        response_text = f"Fantastic! We've set your goal: '{current_goal_info.get('smart_target')}' by '{current_goal_info.get('time_frame')}'. Let's check in regularly to track your progress. What habit related to this goal would you like to track?"
        
        self._memory["conversation_stage"] = "main_menu"
        self._memory.pop("current_goal_info", None)
        self._memory["current_question_index"] = 0
        
        return {"response_text": response_text, "context_update": {"wellness_stage": "goal_set"}, "action": "goal_set"}

    async def _log_habit_activity(self, text: str, nlu_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Logs user habit activity and provides positive reinforcement."""
        logged = False
        response_text = "I'm not sure which habit you're trying to log. Could you be more specific?"
        action = "clarify_habit"

        # Simple habit logging logic
        if "water" in text and ("glass" in text or "cup" in text or "ml" in text):
            count_match = re.search(r'(\d+)\s*(glass|cup|ml|liter)s?', text)
            value = float(count_match.group(1)) if count_match else 1.0
            unit = count_match.group(2) if count_match else "glasses"
            habit_name = "water_intake"
            logged = True
            log_details = {"value": value, "unit": unit}
            response_text = self._update_habit_streak(habit_name, log_details)
        elif "walk" in text or "steps" in text:
            count_match = re.search(r'(\d+)\s*(step|mile)s?', text)
            value = float(count_match.group(1)) if count_match else 5000.0
            unit = count_match.group(2) if count_match else "steps"
            habit_name = "steps_walked"
            logged = True
            log_details = {"value": value, "unit": unit}
            response_text = self._update_habit_streak(habit_name, log_details)
        # FIX: Added "slept" to condition to handle past tense input
        elif ("sleep" in text or "slept" in text) and ("hour" in text or "min" in text):
            duration_match = re.search(r'(\d+)\s*(hour|hr|h|min|m)s?', text)
            value = float(duration_match.group(1)) if duration_match else 7.0
            unit = duration_match.group(2) if duration_match else "hours"
            habit_name = "sleep_duration"
            logged = True
            log_details = {"value": value, "unit": unit}
            response_text = self._update_habit_streak(habit_name, log_details)

        if logged:
            action = "habit_logged"
            if self.habit_tracker_service:
                await self.habit_tracker_service.log_activity(context.get("user_id"), habit_name, log_details)
            self._memory["conversation_stage"] = "main_menu"
            
        return {"response_text": response_text, "context_update": {"wellness_stage": "habit_logged"}, "action": action}

    def _update_habit_streak(self, habit_name: str, log_details: Dict[str, Any]) -> str:
        """Updates habit streak and provides positive reinforcement."""
        today = datetime.date.today()
        habit = self._memory["tracked_habits"].get(habit_name, {"last_logged_date": None, "streak": 0, "total_count": 0, "log_history": []})

        if habit["last_logged_date"] == today:
            return f"You've already logged your {habit_name.replace('_', ' ')} for today! Keep up the great work!"
        
        if habit["last_logged_date"] == today - datetime.timedelta(days=1):
            habit["streak"] += 1
            reinforcement = f"Amazing! You're on a {habit['streak']}-day streak for {habit_name.replace('_', ' ')}!"
        else:
            habit["streak"] = 1
            reinforcement = f"Fantastic! You've started a new streak for {habit_name.replace('_', ' ')}!"

        habit["last_logged_date"] = today
        habit["total_count"] += log_details["value"]
        habit["log_history"].append({"date": today.isoformat(), "details": log_details})
        self._memory["tracked_habits"][habit_name] = habit

        return f"Great job logging your {habit_name.replace('_', ' ')}! {reinforcement}"

    def _provide_health_tip(self) -> Dict[str, Any]:
        """Provides a random health tip."""
        tip = random.choice(self.health_tips)
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": f"Here's a health tip for you: {tip}", "context_update": {"wellness_stage": "tip_provided"}, "action": "provide_tip"}

    def _review_progress(self) -> Dict[str, Any]:
        """Reviews user's goal progress and habit streaks."""
        response_parts = ["Here's an overview of your wellness journey:"]
        
        if not self._memory["wellness_goals"] and not self._memory["tracked_habits"]:
            return {"response_text": "You haven't set any goals or tracked any habits yet. Let's start with a new goal!", "context_update": {}, "action": "offer_goal_setting"}
        
        if self._memory["wellness_goals"]:
            response_parts.append("\n--- Your Goals ---")
            for name, goal in self._memory["wellness_goals"].items():
                response_parts.append(f"- '{goal['target']}' (Target: {goal['time_frame']})")
        
        if self._memory["tracked_habits"]:
            response_parts.append("\n--- Your Habits ---")
            for name, habit in self._memory["tracked_habits"].items():
                response_parts.append(f"- {name.replace('_', ' ').title()}: Last logged {habit['last_logged_date'].strftime('%Y-%m-%d')}. Current streak: {habit['streak']} days. Total logged: {habit['total_count']:.0f}.")
        
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": " ".join(response_parts), "context_update": {"wellness_stage": "progress_reviewed"}, "action": "show_progress"}


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["wellness_goals"] = {}
        self._memory["tracked_habits"] = {}
        self._memory["conversation_stage"] = "greeting"
        self._memory["current_question_index"] = 0
        self._memory.pop("current_goal_info", None)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class MockNLUEngine:
        def process_text(self, text, lang):
            return {}

    class MockHabitTrackerService:
        async def log_activity(self, user_id: str, habit_name: str, details: Dict[str, Any]):
            logger.info(f"MOCK: Logged activity for user {user_id}: {habit_name} - {details}")

    nlu_mock = MockNLUEngine()
    habit_tracker_mock = MockHabitTrackerService()
    
    wellness_agent = WellnessCoachAgent(nlu_engine=nlu_mock, habit_tracker_service=habit_tracker_mock)

    async def run_wellness_flow():
        context = {"call_id": "wellness_call_123", "user_id": "user_well", "language": "en"}

        print("\n--- Flow 1: Set a SMART Goal ---")
        response1 = await wellness_agent.process_input("I want to set a new health goal.", context)
        print(f"Agent: {response1['response_text']}") 
        
        response2 = await wellness_agent.process_input("I want to drink more water.", context)
        print(f"Agent: {response2['response_text']}") 
        
        response3 = await wellness_agent.process_input("I will drink 8 glasses of water every day.", context)
        print(f"Agent: {response3['response_text']}") 
        
        response4 = await wellness_agent.process_input("I will do this for the next 30 days.", context)
        print(f"Agent (Goal Set): {response4['response_text']}")
        assert "Fantastic! We've set your goal" in response4["response_text"]
        assert "drink more water" in wellness_agent.current_memory["wellness_goals"]
        
        print("\n--- Flow 2: Log a Habit ---")
        response5 = await wellness_agent.process_input("I drank 8 glasses of water today.", context)
        print(f"Agent: {response5['response_text']}")
        assert "Amazing! You're on a 1-day streak" in response5["response_text"]
        
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        wellness_agent.current_memory["tracked_habits"]["water_intake"]["last_logged_date"] = datetime.date.today() - datetime.timedelta(days=1) 
        wellness_agent.current_memory["tracked_habits"]["water_intake"]["streak"] = 5
        response6 = await wellness_agent.process_input("I drank 8 glasses of water today again!", context)
        print(f"Agent: {response6['response_text']}")
        assert "on a 6-day streak" in response6["response_text"]

        print("\n--- Flow 3: Get a Health Tip ---")
        response7 = await wellness_agent.process_input("Give me a health tip.", context)
        print(f"Agent: {response7['response_text']}")
        assert "Here's a health tip" in response7["response_text"]

        print("\n--- Flow 4: Review Progress ---")
        response8 = await wellness_agent.process_input("What's my progress?", context)
        print(f"Agent: {response8['response_text']}")
        assert "Your Goals" in response8["response_text"]
        assert "Your Habits" in response8["response_text"]

        wellness_agent.reset_memory()
        print(f"\nMemory after reset: {wellness_agent.current_memory}")

    import asyncio
    asyncio.run(run_wellness_flow())