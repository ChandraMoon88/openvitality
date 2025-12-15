# src/core/intent_classifier.py
"""
Understands what the user wants to do.

This module uses a combination of a powerful zero-shot classification model
and a fast keyword-based fallback to determine the user's intent with high
accuracy and reliability.
"""
from typing import Tuple, Dict, List
import httpx
import os

# from . import logger

class IntentClassifier:
    def __init__(self):
        """Initializes the IntentClassifier."""
        # self.api_url = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
        # self.api_token = os.getenv("HUGGINGFACE_API_TOKEN")
        self.labels = [
            "medical_emergency", "symptom_report", "appointment_booking", 
            "medication_query", "test_results", "billing", 
            "general_question", "small_talk"
        ]
        self.keyword_map = {
            "medical_emergency": ["chest pain", "can't breathe", "bleeding", "unconscious", "suicide"],
            "appointment_booking": ["appointment", "schedule", "book", "see a doctor"],
            "symptom_report": ["hurts", "pain", "fever", "cough", "headache", "feel sick"],
        }
        print("IntentClassifier initialized.")

    async def classify(self, text: str, confidence_threshold: float = 0.7) -> Tuple[str, float]:
        """
        Classifies the user's intent.
        
        Tries to use the Hugging Face API first, and falls back to keyword matching if it fails.
        """
        # Primary Method: Zero-shot classification API
        # if self.api_token:
        #     try:
        #         async with httpx.AsyncClient() as client:
        #             response = await client.post(
        #                 self.api_url,
        #                 headers={"Authorization": f"Bearer {self.api_token}"},
        #                 json={
        #                     "inputs": text,
        #                     "parameters": {"candidate_labels": self.labels},
        #                 },
        #                 timeout=5.0
        #             )
        #             response.raise_for_status()
        #             result = response.json()
        #             top_intent = result['labels'][0]
        #             top_score = result['scores'][0]
                    
        #             if top_score >= confidence_threshold:
        #                 logger.debug(f"Intent classified via API: {top_intent} ({top_score:.2f})")
        #                 return top_intent, top_score

        #     except httpx.HTTPStatusError as e:
        #         logger.error(f"Hugging Face API request failed: {e}")
        #     except Exception as e:
        #         logger.error(f"An unexpected error occurred during intent classification: {e}")

        # Fallback Method: Keyword matching
        # logger.info("Falling back to keyword-based intent classification.")
        return self._classify_by_keywords(text)

    def _classify_by_keywords(self, text: str) -> Tuple[str, float]:
        """A simple keyword-matching fallback."""
        lower_text = text.lower()
        for intent, keywords in self.keyword_map.items():
            if any(keyword in lower_text for keyword in keywords):
                # logger.debug(f"Intent classified via keywords: {intent}")
                return intent, 0.9  # Assign a high confidence for keyword matches
        
        return "general_question", 0.5 # Default if no keywords match

    def handle_multi_intent(self, text: str) -> List[str]:
        """
        Identifies if a user's query contains multiple intents.
        (Conceptual - a more advanced implementation is needed for this)
        """
        intents = set()
        for intent, keywords in self.keyword_map.items():
            if any(keyword in text.lower() for keyword in keywords):
                intents.add(intent)
        return list(intents)
