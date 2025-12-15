
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import pytest
from unittest.mock import patch, MagicMock
from src.language import sentiment_analyzer

# Mock the transformers library being unavailable for some tests
@patch('src.language.sentiment_analyzer.HF_TRANSFORMERS_AVAILABLE', False)
def get_rule_based_analyzer():
    """Returns an analyzer instance where the HF model is disabled."""
    # Reload the module to re-evaluate the HF_TRANSFORMERS_AVAILABLE flag
    from importlib import reload
    reload(sentiment_analyzer)
    return sentiment_analyzer.SentimentAnalyzer()

# Mock the transformers library being available for other tests
@patch('src.language.sentiment_analyzer.HF_TRANSFORMERS_AVAILABLE', True)
@patch('src.language.sentiment_analyzer.pipeline')
def get_model_based_analyzer(mock_pipeline):
    """
    Returns an analyzer instance where the HF pipeline is mocked.
    """
    # Mock the pipeline call to return a function that can be configured in tests
    mock_pipeline.return_value = MagicMock()
    from importlib import reload
    reload(sentiment_analyzer)
    analyzer = sentiment_analyzer.SentimentAnalyzer()
    analyzer.sentiment_pipeline = mock_pipeline.return_value
    return analyzer

class TestSentimentAnalyzerRuleBased:
    """Tests the rule-based logic in isolation."""

    @pytest.fixture
    def analyzer(self):
        return get_rule_based_analyzer()

    def test_panic_keywords(self, analyzer):
        text = "I'm freaking out, I need urgent help!"
        result = analyzer.analyze_sentiment(text)
        assert result['emotional_indicators']['panic'] is True
        assert result['label'] == 'negative'
        assert result['score'] == -0.5

    def test_depression_keywords(self, analyzer):
        text = "Everything feels so hopeless. There is no point."
        result = analyzer.analyze_sentiment(text)
        assert result['emotional_indicators']['depression'] is True
        assert result['label'] == 'negative'
        assert result['score'] == -0.7

    def test_anger_keywords(self, analyzer):
        text = "I'm so pissed off at this."
        result = analyzer.analyze_sentiment(text)
        assert result['emotional_indicators']['anger'] is True
        assert result['label'] == 'negative'
        assert result['score'] == -0.6

    def test_anger_all_caps(self, analyzer):
        text = "WHY IS THIS HAPPENING"
        result = analyzer.analyze_sentiment(text)
        assert result['emotional_indicators']['anger'] is True
        assert result['label'] == 'negative'
        assert result['score'] == -0.6

    def test_pain_intensity_keywords(self, analyzer):
        text = "The pain is excruciating."
        result = analyzer.analyze_sentiment(text)
        assert result['emotional_indicators']['high_pain_intensity'] is True
        # Pain alone doesn't force a negative label, but sets a score floor
        assert result['score'] == -0.4

    def test_no_indicators(self, analyzer):
        text = "Just a regular sentence."
        result = analyzer.analyze_sentiment(text)
        assert not any(result['emotional_indicators'].values())
        assert result['label'] == 'neutral'
        assert result['score'] == 0.0


class TestSentimentAnalyzerModelBased:
    """Tests the model-based logic and its interaction with rules."""

    @pytest.fixture
    def analyzer(self):
        return get_model_based_analyzer()

    def test_model_positive(self, analyzer):
        text = "This is wonderful!"
        # Configure the mock pipeline to return a positive result
        analyzer.sentiment_pipeline.return_value = [{'label': 'POSITIVE', 'score': 0.99}]
        result = analyzer.analyze_sentiment(text)
        assert result['label'] == 'positive'
        assert result['score'] == 0.99

    def test_model_negative(self, analyzer):
        text = "This is terrible."
        # Configure the mock pipeline to return a negative result
        analyzer.sentiment_pipeline.return_value = [{'label': 'NEGATIVE', 'score': 0.98}]
        result = analyzer.analyze_sentiment(text)
        assert result['label'] == 'negative'
        assert result['score'] == -0.98
    
    def test_rule_overrides_model(self, analyzer):
        """Tests that a rule-based indicator overrides a positive model result."""
        text = "This is wonderful, but I'm also starting to panic!"
        # Model sees it as positive
        analyzer.sentiment_pipeline.return_value = [{'label': 'POSITIVE', 'score': 0.9}]
        result = analyzer.analyze_sentiment(text)
        
        # But the panic keyword should override the label and score
        assert result['emotional_indicators']['panic'] is True
        assert result['label'] == 'negative'
        assert result['score'] == -0.5 # Panic rule sets this floor

    def test_empty_string_input(self, analyzer):
        """Tests that an empty string returns a default neutral result."""
        text = " "
        result = analyzer.analyze_sentiment(text)
        assert result['label'] == 'neutral'
        assert result['score'] == 0.0
        assert not any(result['emotional_indicators'].values())

class TestEmpathyTrigger:

    @pytest.fixture
    def analyzer(self):
        # We don't need the model for this, any analyzer will do
        return get_rule_based_analyzer()

    def test_trigger_on_panic(self, analyzer):
        sentiment = {"score": -0.8, "emotional_indicators": {"panic": True, "depression": False, "anger": False, "high_pain_intensity": False}}
        assert analyzer.trigger_empathy_response(sentiment) is True

    def test_trigger_on_strong_negative_score(self, analyzer):
        sentiment = {"score": -0.75, "emotional_indicators": {"panic": False, "depression": False, "anger": False, "high_pain_intensity": False}}
        assert analyzer.trigger_empathy_response(sentiment) is True

    def test_no_trigger_on_neutral(self, analyzer):
        sentiment = {"score": 0.0, "emotional_indicators": {"panic": False, "depression": False, "anger": False, "high_pain_intensity": False}}
        assert analyzer.trigger_empathy_response(sentiment) is False

    def test_no_trigger_on_mild_negative(self, analyzer):
        sentiment = {"score": -0.3, "emotional_indicators": {"panic": False, "depression": False, "anger": False, "high_pain_intensity": False}}
        assert analyzer.trigger_empathy_response(sentiment) is False
