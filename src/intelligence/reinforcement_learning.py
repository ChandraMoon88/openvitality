# src/intelligence/reinforcement_learning.py

from typing import Dict, Any, List
import random
import numpy as np

# Assuming these imports will be available from other modules
# from src.core.dialogue_manager import DialogueManager
# from src.core.telemetry_emitter import TelemetryEmitter


class ReinforcementLearning:
    """
    Implements a reinforcement learning component to allow the AI to learn
    optimal interaction strategies over time through trial and error, based on rewards.
    Uses a simplified Q-learning approach for demonstration.
    """
    def __init__(self, telemetry_emitter_instance, config: Dict[str, Any]):
        """
        Initializes the ReinforcementLearning module.
        
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        :param config: Application configuration for RL parameters.
        """
        self.telemetry = telemetry_emitter_instance
        self.config = config
        
        # Q-learning parameters
        self.learning_rate = config.get("rl_learning_rate", 0.1)
        self.discount_factor = config.get("rl_discount_factor", 0.9)
        self.exploration_rate = config.get("rl_exploration_rate", 0.1) # Epsilon-greedy
        
        # State and Action Space (simplified for a mock example)
        # States could be (intent, session_state, sentiment, medical_safety_flags)
        # Actions could be (ask_clarifying_question, provide_info, transfer_to_human, book_appointment)
        self.states = [
            "start", "triage_in_progress", "booking_in_progress",
            "medical_info_provided", "user_frustrated", "session_ended_success", "session_ended_fail"
        ]
        self.actions = [
            "ask_clarifying_question", "provide_medical_info", "transfer_to_human",
            "suggest_booking", "end_session_gracefully", "repeat_last_response"
        ]
        
        # Q-table: {state: {action: Q_value}}
        self.q_table: Dict[str, Dict[str, float]] = self._initialize_q_table()
        
        print("✅ ReinforcementLearning initialized.")

    def _initialize_q_table(self) -> Dict[str, Dict[str, float]]:
        """Initializes the Q-table with zeros or small random values."""
        q_table = {}
        for state in self.states:
            q_table[state] = {action: 0.0 for action in self.actions}
        return q_table

    def get_action(self, current_state: str) -> str:
        """
        Selects an action based on the current state using an epsilon-greedy policy.
        
        :param current_state: The current state of the dialogue/session.
        :return: The chosen action.
        """
        if current_state not in self.q_table:
            self.q_table[current_state] = {action: 0.0 for action in self.actions}
            print(f"⚠️ RL: New state '{current_state}' encountered. Initializing Q-values.")

        if random.uniform(0, 1) < self.exploration_rate:
            # Explore: choose a random action
            action = random.choice(self.actions)
            self.telemetry.emit_event("rl_action_exploration", {"state": current_state, "action": action})
        else:
            # Exploit: choose the action with the highest Q-value
            q_values = self.q_table[current_state]
            # Handle case where all Q-values are the same (e.g., all zeros)
            max_q = max(q_values.values())
            best_actions = [action for action, q_val in q_values.items() if q_val == max_q]
            action = random.choice(best_actions) # Break ties randomly
            self.telemetry.emit_event("rl_action_exploitation", {"state": current_state, "action": action})
        
        print(f"RL chose action: {action} for state: {current_state}")
        return action

    def update_policy(self, state: str, action: str, reward: float, next_state: str):
        """
        Updates the Q-table based on the observed reward and next state.
        
        :param state: The previous state.
        :param action: The action taken.
        :param reward: The reward received for taking the action in the previous state.
        :param next_state: The new state after taking the action.
        """
        if state not in self.q_table:
            self.q_table[state] = {a: 0.0 for a in self.actions}
        if next_state not in self.q_table:
            self.q_table[next_state] = {a: 0.0 for a in self.actions}

        old_q_value = self.q_table[state][action]
        next_max_q_value = max(self.q_table[next_state].values())
        
        new_q_value = (1 - self.learning_rate) * old_q_value + \
                      self.learning_rate * (reward + self.discount_factor * next_max_q_value)
        
        self.q_table[state][action] = new_q_value
        
        self.telemetry.emit_event(
            "rl_policy_update",
            {
                "state": state,
                "action": action,
                "reward": reward,
                "next_state": next_state,
                "old_q": old_q_value,
                "new_q": new_q_value
            }
        )
        print(f"RL policy updated for state '{state}', action '{action}'. New Q-value: {new_q_value:.4f}")

    def get_reward(self, session_context: Dict[str, Any], action_taken: str, user_feedback: float = 0.0) -> float:
        """
        Calculates a reward based on the outcome of an interaction.
        This is a critical part of ethical RL, ensuring rewards align with goals.
        
        :param session_context: The context after the interaction.
        :param action_taken: The action that was just taken.
        :param user_feedback: Optional explicit feedback from the user (-1 to 1).
        :return: The calculated reward.
        """
        reward = 0.0
        
        # Positive rewards
        if session_context.get("session_ended_successfully"):
            reward += 10.0
            print("Rewarded +10 for successful session end.")
        if action_taken == "transfer_to_human" and session_context.get("user_escalated_successfully"):
            reward += 5.0
            print("Rewarded +5 for successful human transfer.")
        if action_taken == "suggest_booking" and session_context.get("appointment_booked"):
            reward += 7.0
            print("Rewarded +7 for successful appointment booking.")

        # Negative rewards
        if session_context.get("user_frustrated"):
            reward -= 5.0
            print("Penalized -5 for user frustration.")
        if session_context.get("medical_misinformation_flagged"):
            reward -= 20.0 # Huge penalty for safety violations
            print("Penalized -20 for medical misinformation.")
        if action_taken == "end_session_gracefully" and not session_context.get("user_satisfied"):
            reward -= 2.0
            print("Penalized -2 for unsatisfactory graceful end.")

        # Incorporate explicit user feedback
        reward += user_feedback * 3.0 # Scale user feedback
        
        return reward

# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_te = MockTelemetryEmitter()
    mock_config = {
        "rl_learning_rate": 0.1,
        "rl_discount_factor": 0.9,
        "rl_exploration_rate": 0.2 # Higher for demo to see exploration
    }
    
    rl_agent = ReinforcementLearning(mock_te, mock_config)

    # --- Simulation of an interaction ---
    print("\n--- RL Interaction Simulation ---")
    
    current_state = "start"
    session_id = "rl_session_1"
    
    for _ in range(5): # Simulate 5 turns
        print(f"\n--- Turn {_ + 1} ---")
        action = rl_agent.get_action(current_state)
        
        # Simulate environment response (next_state and rewards)
        next_state = current_state
        reward = 0.0
        session_context = {"session_id": session_id}

        if action == "ask_clarifying_question":
            if random.random() < 0.7: # 70% chance user gives more info
                next_state = "triage_in_progress"
                reward += 1.0
            else:
                next_state = "user_frustrated"
                reward -= 1.0
            
        elif action == "suggest_booking":
            if random.random() < 0.5: # 50% chance user books
                session_context["appointment_booked"] = True
                next_state = "booking_in_progress"
                reward += 2.0
            else:
                next_state = "user_frustrated"
                reward -= 1.0
        
        elif action == "transfer_to_human":
            session_context["user_escalated_successfully"] = True
            next_state = "session_ended_success"
            reward += 3.0
            
        elif action == "end_session_gracefully":
            if random.random() < 0.8:
                session_context["session_ended_successfully"] = True
                reward += 5.0
            else:
                session_context["user_satisfied"] = False
                session_context["session_ended_successfully"] = True # Session still ends
                reward -= 2.0
        
        calculated_reward = rl_agent.get_reward(session_context, action, user_feedback=0.0) # No explicit user feedback
        reward += calculated_reward

        rl_agent.update_policy(current_state, action, reward, next_state)
        current_state = next_state
        
        if current_state in ["session_ended_success", "session_ended_fail"]:
            print(f"Session ended in state: {current_state}")
            break

    print("\n--- Final Q-table (after simulation) ---")
    for state, actions_q_values in rl_agent.q_table.items():
        print(f"State: {state}")
        for action, q_value in actions_q_values.items():
            print(f"  {action}: {q_value:.4f}")
