
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from src.core.intent_classifier import IntentClassifier

@pytest.fixture
def classifier():
    """Provides an instance of IntentClassifier for testing."""
    return IntentClassifier()

def test_initialization(classifier):
    """Tests that the classifier initializes with expected labels and keywords."""
    assert "appointment_booking" in classifier.labels
    assert "appointment_booking" in classifier.keyword_map

@pytest.mark.asyncio
async def test_classify_appointment(classifier):
    """Tests classification of an appointment booking intent."""
    text = "I need to schedule an appointment for next week."
    intent, score = await classifier.classify(text)
    assert intent == "appointment_booking"
    assert score == 0.9

@pytest.mark.asyncio
async def test_classify_symptom_report(classifier):
    """Tests classification of a symptom report intent."""
    text = "My head hurts and I have a high fever."
    intent, score = await classifier.classify(text)
    assert intent == "symptom_report"
    assert score == 0.9

@pytest.mark.asyncio
async def test_classify_emergency(classifier):
    """Tests classification of a medical emergency intent."""
    text = "Help, I think I'm having a heart attack, I have chest pain!"
    intent, score = await classifier.classify(text)
    assert intent == "medical_emergency"
    assert score == 0.9
    
@pytest.mark.asyncio
async def test_classify_case_insensitivity(classifier):
    """Tests that classification is case-insensitive."""
    text = "I want to BOOK AN APPOINTMENT."
    intent, score = await classifier.classify(text)
    assert intent == "appointment_booking"
    assert score == 0.9

@pytest.mark.asyncio
async def test_classify_default_general_question(classifier):
    """Tests the default classification for unknown intents."""
    text = "What is the weather like today?"
    intent, score = await classifier.classify(text)
    assert intent == "general_question"
    assert score == 0.5

@pytest.mark.asyncio
async def test_classify_no_clear_intent(classifier):
    """Tests another case of a general question."""
    text = "Can you tell me more about this hospital?"
    intent, score = await classifier.classify(text)
    assert intent == "general_question"
    assert score == 0.5

def test_handle_multi_intent_single(classifier):
    """Tests multi-intent detection for a single intent."""
    text = "I feel sick."
    intents = classifier.handle_multi_intent(text)
    assert intents == ["symptom_report"]

def test_handle_multi_intent_multiple(classifier):
    """Tests multi-intent detection for multiple intents."""
    text = "I have a bad cough and I need to schedule a visit."
    intents = classifier.handle_multi_intent(text)
    # The order is not guaranteed, so we check for presence and length
    assert "symptom_report" in intents
    assert "appointment_booking" in intents
    assert len(intents) == 2

def test_handle_multi_intent_none(classifier):
    """Tests multi-intent detection when no keywords are found."""
    text = "Thank you for your help."
    intents = classifier.handle_multi_intent(text)
    assert intents == []

# Note: The primary API-based classification is currently commented out in the source.
# When it's enabled, we will need to add tests that mock the httpx client
# and test the API response handling, confidence thresholds, and fallback logic.

