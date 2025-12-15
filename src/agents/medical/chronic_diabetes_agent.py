import logging
import datetime
import statistics
from typing import Dict, Any, List, Optional
import re

from src.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

class ChronicDiabetesAgent(BaseAgent):
    """
    A specialized AI agent for long-term glucose management in chronic diabetes patients.
    It assists with daily logging, trend analysis, alerts for critical hypo/hyperglycemia events,
    and provides reminders for care and screenings.
    """
    def __init__(self, nlu_engine: Any = None, task_scheduler: Any = None):
        super().__init__(
            name="ChronicDiabetesAgent",
            description="Assists with long-term glucose management and diabetes care.",
            persona={
                "role": "supportive and informative diabetes care assistant",
                "directives": [
                    "Encourage consistent glucose monitoring and logging.",
                    "Provide insights on glucose trends over time.",
                    "Alert immediately to critical hypo/hyperglycemia events.",
                    "Offer evidence-based advice on diet, exercise, and medication adherence.",
                    "Remind about essential self-care (foot checks) and medical screenings (eye exams).",
                    "Emphasize consulting healthcare professionals for any changes in condition or treatment."
                ],
                "style": "patient, encouraging, factual"
            }
        )
        self.nlu_engine = nlu_engine
        self.task_scheduler = task_scheduler
        
        self._memory["glucose_readings"] = [] # List of {"timestamp": dt, "type": "fasting"/"post_meal", "value": val}
        self._memory["a1c_estimates"] = [] # List of {"timestamp": dt, "estimate": val}
        self._memory["activity_log"] = [] # List of {"timestamp": dt, "type": "food"/"exercise", "details": {}}
        self._memory["last_foot_check_reminder"] = None
        self._memory["last_eye_exam_reminder"] = None
        
        self._memory["conversation_stage"] = "greeting" # greeting, logging_glucose, carb_counting, reminders
        
        # Hypoglycemia and Hyperglycemia thresholds (mg/dL)
        self.hypo_threshold = 70
        self.hyper_threshold = 250
        logger.info("ChronicDiabetesAgent initialized.")

    async def process_input(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes user input related to diabetes management.
        """
        if not await self._check_safety(text):
            return {"response_text": "I cannot process that request due to safety concerns.", "context_update": {}, "action": "escalate_to_human"}

        nlu_output = {}
        if self.nlu_engine:
            nlu_output = await self.nlu_engine.process_text(text, context.get("language", "en"))
        
        text_lower = text.lower()

        if self._memory["conversation_stage"] == "greeting":
            self._memory["conversation_stage"] = "main_menu"
            return {
                "response_text": "Hello, I'm here to help you manage your diabetes. Would you like to log a glucose reading, get advice on diet or exercise, or hear your latest trends?",
                "context_update": {"diabetes_stage": "main_menu"},
                "action": "prompt_main_menu"
            }
        
        elif self._memory["conversation_stage"] == "main_menu":
            if "log glucose" in text_lower or "sugar reading" in text_lower:
                self._memory["conversation_stage"] = "logging_glucose"
                return {"response_text": "Please tell me your glucose reading and whether it was fasting or post-meal.", "context_update": {"diabetes_stage": "ask_glucose_reading"}, "action": "ask_glucose"}
            elif "trends" in text_lower or "history" in text_lower:
                return self._provide_glucose_trends()
            elif "a1c" in text_lower or "estimated a1c" in text_lower:
                return self._estimate_a1c()
            elif "diet" in text_lower or "carb counting" in text_lower:
                return self._provide_diet_advice()
            elif "exercise" in text_lower or "activity" in text_lower:
                return self._provide_exercise_advice()
            # FIX: Added 'remind' to trigger condition so general reminders are caught
            elif "foot check" in text_lower or "eye exam" in text_lower or "remind" in text_lower:
                return await self._provide_reminders(text_lower, context)
        
        elif self._memory["conversation_stage"] == "logging_glucose":
            return self._log_glucose_reading(text_lower, nlu_output, context)
            
        return {"response_text": "I didn't quite understand that. Please tell me if you want to log a reading, check trends, or get advice.", "context_update": {}, "action": "clarify_diabetes"}

    def _log_glucose_reading(self, text: str, nlu_output: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Logs a new glucose reading and checks for hypo/hyperglycemia."""
        glucose_value = None
        reading_type = "general" # fasting, post_meal, general

        # Extract glucose value (conceptual - needs robust NLU/entity extraction for numbers)
        value_match = re.search(r'(\d+)\s*(mg/dl|mg/dL)?', text, re.IGNORECASE)
        if value_match:
            glucose_value = int(value_match.group(1))
        
        if "fasting" in text:
            reading_type = "fasting"
        elif "post-meal" in text or "after eating" in text:
            reading_type = "post_meal"

        if glucose_value:
            reading = {"timestamp": datetime.datetime.now(), "type": reading_type, "value": glucose_value}
            self._memory["glucose_readings"].append(reading)
            self._memory["glucose_readings"] = sorted(self._memory["glucose_readings"], key=lambda x: x["timestamp"]) # Keep sorted

            response_text = f"Logged your {reading_type} glucose reading of {glucose_value} mg/dL."
            action = "glucose_logged"

            # Check for hypo/hyperglycemia
            if glucose_value < self.hypo_threshold:
                response_text += " This is a low blood sugar (hypoglycemic) reading. Please follow your doctor's instructions for hypoglycemia, such as consuming fast-acting carbohydrates. Seek medical help if you feel unwell or confused."
                action = "alert_hypoglycemia"
            elif glucose_value > self.hyper_threshold:
                response_text += " This is a high blood sugar (hyperglycemic) reading. Please follow your doctor's instructions for hyperglycemia, and monitor your symptoms. If symptoms are severe or persistent, seek medical attention."
                action = "alert_hyperglycemia"
            
            self._memory["conversation_stage"] = "main_menu"
            return {"response_text": response_text, "context_update": {"diabetes_stage": "reading_logged", "alert": action}, "action": action}
        else:
            return {"response_text": "I couldn't find a clear glucose reading in your message. Please tell me the number.", "context_update": {"diabetes_stage": "ask_glucose_reading_retry"}, "action": "ask_glucose_retry"}


    def _provide_glucose_trends(self) -> Dict[str, Any]:
        """Analyzes and provides glucose trends over recent periods."""
        if not self._memory["glucose_readings"]:
            return {"response_text": "I don't have enough glucose readings to provide trends. Please log some readings first.", "context_update": {}, "action": "no_data"}

        last_30_days = [r["value"] for r in self._memory["glucose_readings"] if (datetime.datetime.now() - r["timestamp"]).days <= 30]
        last_90_days = [r["value"] for r in self._memory["glucose_readings"] if (datetime.datetime.now() - r["timestamp"]).days <= 90]

        response_parts = []
        if last_30_days:
            avg_30 = round(statistics.mean(last_30_days), 1)
            response_parts.append(f"Over the last 30 days, your average glucose reading is {avg_30} mg/dL.")
        if last_90_days:
            avg_90 = round(statistics.mean(last_90_days), 1)
            response_parts.append(f"Over the last 90 days, your average glucose reading is {avg_90} mg/dL.")
        
        hypo_count = sum(1 for r in self._memory["glucose_readings"] if r["value"] < self.hypo_threshold)
        hyper_count = sum(1 for r in self._memory["glucose_readings"] if r["value"] > self.hyper_threshold)
        
        if hypo_count > 0: response_parts.append(f"You have recorded {hypo_count} hypoglycemic events (<{self.hypo_threshold} mg/dL).")
        if hyper_count > 0: response_parts.append(f"You have recorded {hyper_count} hyperglycemic events (>{self.hyper_threshold} mg/dL).")

        response_text = " ".join(response_parts) if response_parts else "No sufficient data for trends."
        response_text += " Please discuss these trends with your doctor."

        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"diabetes_stage": "trends_provided"}, "action": "display_trends"}

    def _estimate_a1c(self) -> Dict[str, Any]:
        """Estimates A1C from average glucose readings."""
        # Estimated A1C (%) = (Average Glucose mg/dL + 46.7) / 28.7
        if not self._memory["glucose_readings"] or len(self._memory["glucose_readings"]) < 14: # Need at least 2 weeks of data
            return {"response_text": "I need at least two weeks of glucose readings to provide an A1C estimate. Please log more readings.", "context_update": {}, "action": "no_a1c_data"}
        
        all_readings = [r["value"] for r in self._memory["glucose_readings"]]
        avg_glucose = statistics.mean(all_readings)
        estimated_a1c = (avg_glucose + 46.7) / 28.7
        
        self._memory["a1c_estimates"].append({"timestamp": datetime.datetime.now(), "estimate": estimated_a1c})

        response_text = f"Based on your recorded glucose readings, your estimated A1C is approximately {estimated_a1c:.1f}%. " \
                        "This is an estimate and should be confirmed by a lab test. Discuss this with your doctor."
        
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"diabetes_stage": "a1c_estimated"}, "action": "display_a1c"}

    def _provide_diet_advice(self) -> Dict[str, Any]:
        """Provides general advice on diet and carb counting."""
        response_text = (
            "For diabetes management, focusing on balanced meals, controlled portions, and consistent carbohydrate intake is important. "
            "Prioritize whole grains, lean proteins, fruits, and vegetables. "
            "Carb counting can help manage blood sugar; generally, aim for 45-60 grams of carbohydrates per meal, but this can vary. "
            "Consult a registered dietitian for personalized meal planning. (Source: American Diabetes Association)"
        )
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"diabetes_stage": "diet_advice"}, "action": "display_advice"}

    def _provide_exercise_advice(self) -> Dict[str, Any]:
        """Provides general advice on exercise and its impact on glucose."""
        response_text = (
            "Regular physical activity is vital for diabetes management. Aim for at least 150 minutes of moderate-intensity aerobic activity per week, along with strength training. "
            "Exercise can lower blood sugar, so monitor your levels closely, especially when starting a new routine, to prevent hypoglycemia. "
            "Always consult your doctor before starting any new exercise program. (Source: American Diabetes Association)"
        )
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"diabetes_stage": "exercise_advice"}, "action": "display_advice"}

    async def _provide_reminders(self, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provides reminders for foot care and eye exams."""
        response_parts = []
        user_id = context.get("user_id")
        if "foot check" in text:
            response_parts.append("Daily foot checks are crucial for preventing complications. Look for cuts, blisters, redness, swelling, or any changes. If you notice anything unusual, contact your doctor. I can set a daily reminder for this.")
            if self.task_scheduler:
                await self.task_scheduler.schedule_daily_reminder("foot_check", user_id)
                self._memory["last_foot_check_reminder"] = datetime.datetime.now()
                response_parts.append("A daily foot check reminder has been set.")
        if "eye exam" in text:
            response_parts.append("An annual dilated eye exam is essential to screen for diabetic retinopathy, a serious eye condition. If you haven't had one in the last year, please schedule one. I can set an annual reminder.")
            if self.task_scheduler:
                await self.task_scheduler.schedule_annual_reminder("eye_exam", user_id)
                self._memory["last_eye_exam_reminder"] = datetime.datetime.now()
                response_parts.append("An annual eye exam reminder has been set.")

        response_text = " ".join(response_parts) if response_parts else "What kind of reminder are you looking for?"
        self._memory["conversation_stage"] = "main_menu"
        return {"response_text": response_text, "context_update": {"diabetes_stage": "reminders_provided"}, "action": "display_reminders"}


    def reset_memory(self):
        """Resets the agent's memory for a new session."""
        super().reset_memory()
        self._memory["glucose_readings"] = []
        self._memory["a1c_estimates"] = []
        self._memory["activity_log"] = []
        self._memory["last_foot_check_reminder"] = None
        self._memory["last_eye_exam_reminder"] = None
        self._memory["conversation_stage"] = "greeting"

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Mock dependencies
    class MockNLUEngine:
        def process_text(self, text, lang):
            return {} # Simplified for this example

    class MockTaskScheduler:
        async def schedule_task(self, task_type: str, due_time: datetime.datetime, payload: Dict[str, Any]):
            logger.info(f"MOCK: Scheduled {task_type} for {due_time} with payload {payload}")

    nlu_mock = MockNLUEngine()
    task_scheduler_mock = MockTaskScheduler()
    
    diabetes_agent = ChronicDiabetesAgent(nlu_engine=nlu_mock, task_scheduler=task_scheduler_mock)

    async def run_diabetes_flow():
        context = {"call_id": "diabetes_call", "user_id": "user_diab", "language": "en"}

        print("\n--- Flow 1: Log Glucose Reading (Normal) ---")
        response1 = await diabetes_agent.process_input("Hello, I want to log my glucose.", context)
        print(f"Agent: {response1['response_text']}")
        
        response2 = await diabetes_agent.process_input("My fasting sugar was 120.", context)
        print(f"Agent: {response2['response_text']}")
        assert len(diabetes_agent.current_memory["glucose_readings"]) == 1

        print("\n--- Flow 2: Log Glucose Reading (Hypoglycemic) ---")
        response3 = await diabetes_agent.process_input("Log my sugar: 65.", context)
        print(f"Agent: {response3['response_text']}")
        assert "low blood sugar" in response3["response_text"]

        print("\n--- Flow 3: Log Glucose Reading (Hyperglycemic) ---")
        response4 = await diabetes_agent.process_input("My post-meal reading was 280.", context)
        print(f"Agent: {response4['response_text']}")
        assert "high blood sugar" in response4["response_text"]

        # Simulate adding enough data for trends and A1C
        for _ in range(15):
            diabetes_agent._memory["glucose_readings"].append({"timestamp": datetime.datetime.now() - datetime.timedelta(days=_), "type": "fasting", "value": 130 + _*2})
            diabetes_agent._memory["glucose_readings"].append({"timestamp": datetime.datetime.now() - datetime.timedelta(days=_), "type": "post_meal", "value": 180 + _*3})


        print("\n--- Flow 4: Provide Trends ---")
        response_trends = await diabetes_agent.process_input("What are my glucose trends?", context)
        print(f"Agent: {response_trends['response_text']}")
        assert "average glucose reading" in response_trends["response_text"]

        print("\n--- Flow 5: Estimate A1C ---")
        response_a1c = await diabetes_agent.process_input("Can you estimate my A1C?", context)
        print(f"Agent: {response_a1c['response_text']}")
        assert "estimated A1C is approximately" in response_a1c["response_text"]

        print("\n--- Flow 6: Diet Advice ---")
        response_diet = await diabetes_agent.process_input("Tell me about carb counting.", context)
        print(f"Agent: {response_diet['response_text']}")
        assert "balanced meals" in response_diet["response_text"]

        print("\n--- Flow 7: Exercise Advice ---")
        response_exercise = await diabetes_agent.process_input("What about exercise?", context)
        print(f"Agent: {response_exercise['response_text']}")
        assert "physical activity" in response_exercise["response_text"]

        print("\n--- Flow 8: Foot Check Reminder ---")
        response_foot = await diabetes_agent.process_input("Remind me about foot checks.", context)
        print(f"Agent: {response_foot['response_text']}")
        assert "daily foot checks are crucial" in response_foot["response_text"]

        diabetes_agent.reset_memory()
        print(f"\nMemory after reset: {diabetes_agent.current_memory}")

    import asyncio
    asyncio.run(run_diabetes_flow())