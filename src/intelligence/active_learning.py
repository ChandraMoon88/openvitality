# src/intelligence/active_learning.py

import json
from typing import Dict, Any, List
import time
import datetime
import asyncio

# Assuming these imports will be available from other modules
# from src.core.telemetry_emitter import TelemetryEmitter
# from src.core.priority_queue import PriorityQueue # For managing review queue


class ActiveLearning:
    """
    Implements active learning by identifying AI predictions with low confidence
    or high uncertainty and flagging them for human review. This feedback loop
    helps continuously improve AI models.
    """
    def __init__(self, telemetry_emitter_instance, review_queue_instance, config: Dict[str, Any]):
        """
        Initializes the ActiveLearning module.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param review_queue_instance: An initialized PriorityQueue instance for human review tasks.
        :param config: Application configuration, including confidence thresholds.
        """
        self.telemetry = telemetry_emitter_instance
        self.review_queue = review_queue_instance
        self.config = config
        
        # Confidence thresholds for flagging (can be adjusted per component)
        self.confidence_thresholds = config.get("active_learning_thresholds", {
            "intent_classification": 0.7,
            "entity_extraction": 0.6,
            "medical_fact_check": 0.75, # Lower confidence in fact check needs review
            "nlu_overall": 0.65
        })
        
        print("✅ ActiveLearning initialized.")

    async def flag_for_review(self, prediction_data: Dict[str, Any], session_id: str, user_id: str = None) -> None:
        """
        Flags a prediction for human review if its confidence falls below
        a predefined threshold or if it exhibits high uncertainty.
        
        :param prediction_data: A dictionary containing the prediction details,
                                including 'type', 'value', and 'confidence'.
        :param session_id: The ID of the session where the prediction occurred.
        :param user_id: The ID of the user associated with the session.
        """
        prediction_type = prediction_data.get("type", "unknown")
        confidence = prediction_data.get("confidence", 1.0)
        
        threshold = self.confidence_thresholds.get(prediction_type, 0.8) # Default high threshold
        
        if confidence < threshold:
            review_task = {
                "task_id": f"review-{session_id}-{prediction_type}-{time.time_ns()}",
                "session_id": session_id,
                "user_id": user_id,
                "prediction_type": prediction_type,
                "prediction_details": prediction_data,
                "reason_for_review": f"Low confidence ({confidence:.2f} < {threshold:.2f})",
                "timestamp": datetime.datetime.now().isoformat(),
                "status": "pending_review"
            }
            
            # Add to review queue with a priority (e.g., higher priority for lower confidence)
            priority = int((1.0 - confidence) * 100) # Higher priority for lower confidence
            await self.review_queue.add_task(review_task, priority=priority)
            
            self.telemetry.emit_event("active_learning_flagged", review_task)
            print(f"🚩 Prediction of type '{prediction_type}' flagged for human review (confidence: {confidence:.2f}).")
        else:
            print(f"Prediction of type '{prediction_type}' within acceptable confidence ({confidence:.2f}).")

    async def _process_feedback(self, feedback_data: Dict[str, Any]) -> None:
        """
        Processes human feedback for a previously flagged prediction.
        This would trigger model retraining or data updates.
        
        :param feedback_data: A dictionary containing the original prediction and human correction.
        """
        task_id = feedback_data.get("task_id")
        human_correction = feedback_data.get("correction")
        
        print(f"Received human feedback for task {task_id}: {human_correction}")
        
        # Here, you would trigger:
        # 1. Update to training dataset
        # 2. Potential fine-tuning of relevant models (e.g., intent classifier)
        # 3. Log the feedback for model improvement metrics
        
        self.telemetry.emit_event(
            "active_learning_feedback_processed",
            {
                "task_id": task_id,
                "status": "processed",
                "correction": human_correction
            }
        )
        print(f"Feedback for task {task_id} processed. This would typically update models.")

    async def get_next_review_task(self) -> Dict[str, Any] | None:
        """
        Retrieves the next highest-priority task from the review queue.
        This would be consumed by an external human annotation tool.
        """
        task = await self.review_queue.get_next_task()
        if task:
            print(f"Fetched next review task: {task.get('prediction_type')}")
        return task


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    class MockPriorityQueue:
        def __init__(self):
            self._queue = []
        async def add_task(self, task: Dict, priority: int):
            self._queue.append({"task": task, "priority": priority})
            self._queue.sort(key=lambda x: x["priority"], reverse=True) # Higher priority first
            print(f"MockPQ: Added task with priority {priority}. Queue size: {len(self._queue)}")
        async def get_next_task(self) -> Dict | None:
            if self._queue:
                return self._queue.pop(0)["task"]
            return None
        async def remove_task(self, task_id: str):
            self._queue = [t for t in self._queue if t["task"]["task_id"] != task_id]


    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    mock_pq = MockPriorityQueue()
    mock_config = {
        "active_learning_thresholds": {
            "intent_classification": 0.7,
            "entity_extraction": 0.6,
            "medical_fact_check": 0.75,
            "nlu_overall": 0.65
        }
    }
    
    active_learner = ActiveLearning(mock_te, mock_pq, mock_config)

    # --- Test 1: Flag a low-confidence intent ---
    print("\n--- Test 1: Flag a low-confidence intent ---")
    prediction1 = {"type": "intent_classification", "value": "appointment_booking", "confidence": 0.6}
    asyncio.run(active_learner.flag_for_review(prediction1, "session_001", "user_abc"))

    # --- Test 2: Flag a high-confidence intent (should not be flagged) ---
    print("\n--- Test 2: Flag a high-confidence intent ---")
    prediction2 = {"type": "intent_classification", "value": "medical_emergency", "confidence": 0.95}
    asyncio.run(active_learner.flag_for_review(prediction2, "session_002", "user_def"))

    # --- Test 3: Flag a low-confidence entity extraction ---
    print("\n--- Test 3: Flag a low-confidence entity extraction ---")
    prediction3 = {"type": "entity_extraction", "value": "Tylenol", "confidence": 0.55}
    asyncio.run(active_learner.flag_for_review(prediction3, "session_003", "user_ghi"))

    # --- Test 4: Retrieve next task ---
    print("\n--- Test 4: Retrieve next task ---")
    next_task = asyncio.run(active_learner.get_next_review_task())
    print(f"Next task for review: {json.dumps(next_task, indent=2)}")

    # --- Test 5: Simulate processing feedback ---
    print("\n--- Test 5: Simulate processing feedback ---")
    if next_task:
        feedback_data = {
            "task_id": next_task["task_id"],
            "original_prediction": next_task["prediction_details"],
            "correction": {"value": "appointment_scheduling", "confidence": 1.0, "reason": "User explicitly stated"}
        }
        asyncio.run(active_learner._process_feedback(feedback_data))