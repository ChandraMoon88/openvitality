import logging
import re
from typing import Dict, Any, Optional

try:
    from transformers import pipeline
    HF_TRANSFORMERS_AVAILABLE = True
except ImportError:
    HF_TRANSFORMERS_AVAILABLE = False
    logging.warning("Hugging Face Transformers not installed. Model-based sentiment analysis will be unavailable.")

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    """
    Detects the user's emotional state from text input.
    Uses a pre-trained Hugging Face model for general sentiment and
    rule-based methods for specific emotional indicators (panic, depression, anger).
    """
    def __init__(self,
                 hf_model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
        self.sentiment_pipeline = None
        if HF_TRANSFORMERS_AVAILABLE:
            try:
                # This model typically outputs 'POSITIVE' or 'NEGATIVE' with scores
                self.sentiment_pipeline = pipeline("sentiment-analysis", model=hf_model_name)
                logger.info(f"Hugging Face sentiment analysis pipeline '{hf_model_name}' loaded.")
            except Exception as e:
                logger.error(f"Failed to load Hugging Face model '{hf_model_name}': {e}. Model-based sentiment analysis disabled.")
                self.sentiment_pipeline = None
        
        # Rule-based detection keywords
        self.panic_keywords = re.compile(r'\b(panic|terrified|can\'t cope|freaking out|urgent help)\b', re.IGNORECASE)
        self.depression_indicators = re.compile(r'\b(hopeless|worthless|empty|forever|no point|end it all|can\'t go on)\b', re.IGNORECASE)
        self.anger_keywords = re.compile(r'\b(angry|furious|pissed|mad|hate|damn|hell)\b', re.IGNORECASE)
        self.pain_intensity_keywords = re.compile(r'\b(unbearable|excruciating|severe|intense|sharp|crushing)\b', re.IGNORECASE)

        logger.info("SentimentAnalyzer initialized.")

    def analyze_sentiment(self, text: str, lang_code: str = "en") -> Dict[str, Any]:
        """
        Analyzes the sentiment of the given text.

        Args:
            text (str): The input text to analyze.
            lang_code (str): The language code of the text (currently only 'en' supported for model).

        Returns:
            Dict[str, Any]: A dictionary containing 'label' (e.g., 'positive', 'negative', 'neutral')
                            and 'score' (-1 to +1). Also includes specific emotional indicators.
        """
        result = {
            "label": "neutral",
            "score": 0.0, # -1 (very negative) to +1 (very positive)
            "emotional_indicators": {
                "panic": False,
                "depression": False,
                "anger": False,
                "high_pain_intensity": False
            }
        }
        if not text.strip():
            return result

        # 1. Model-based general sentiment (English only for this specific model)
        if self.sentiment_pipeline and lang_code == "en":
            try:
                hf_output = self.sentiment_pipeline(text)[0]
                if hf_output['label'] == 'POSITIVE':
                    result['label'] = 'positive'
                    result['score'] = hf_output['score']
                else: # 'NEGATIVE'
                    result['label'] = 'negative'
                    result['score'] = -hf_output['score']
            except Exception as e:
                logger.warning(f"Sentiment model failed for '{text}': {e}. Falling back to rule-based.")

        # 2. Rule-based specific emotional indicators (can be multilingual with appropriate keywords)
        text_lower = text.lower()

        if self.panic_keywords.search(text_lower):
            result["emotional_indicators"]["panic"] = True
            if result["score"] > -0.5: result["score"] = -0.5 # Push towards negative
            result["label"] = "negative" # Overwrite if needed
            logger.debug(f"Panic detected for: '{text}'")

        if self.depression_indicators.search(text_lower):
            result["emotional_indicators"]["depression"] = True
            if result["score"] > -0.7: result["score"] = -0.7 # Push heavily negative
            result["label"] = "negative"
            logger.debug(f"Depression indicators detected for: '{text}'")

        if self.anger_keywords.search(text_lower) or (text.isupper() and len(text) > 5): # Check for ALL CAPS
            result["emotional_indicators"]["anger"] = True
            if result["score"] > -0.6: result["score"] = -0.6 # Push towards negative
            result["label"] = "negative"
            logger.debug(f"Anger detected for: '{text}'")

        if self.pain_intensity_keywords.search(text_lower):
            result["emotional_indicators"]["high_pain_intensity"] = True
            if result["score"] > -0.4: result["score"] = -0.4 # Indicate concern
            logger.debug(f"High pain intensity detected for: '{text}'")

        # Adjust score for neutral if no strong indicators and model didn't classify strongly
        if abs(result["score"]) < 0.2 and not any(result["emotional_indicators"].values()):
            result["label"] = "neutral"
            result["score"] = 0.0

        logger.debug(f"Sentiment for '{text}': {json.dumps(result)}")
        return result

    def trigger_empathy_response(self, sentiment_result: Dict[str, Any]) -> bool:
        """
        Determines if an empathy-triggering response is needed based on sentiment.
        """
        if sentiment_result["emotional_indicators"]["panic"] or \
           sentiment_result["emotional_indicators"]["depression"] or \
           sentiment_result["emotional_indicators"]["anger"] or \
           sentiment_result["emotional_indicators"]["high_pain_intensity"] or \
           sentiment_result["score"] < -0.5:
            logger.info("Empathy response triggered due to detected negative sentiment/emotional indicators.")
            return True
        return False

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    analyzer = SentimentAnalyzer()

    # Test cases
    print("\n--- Test Case 1: Positive Sentiment ---")
    text1 = "Thank you so much, I feel much better now!"
    sentiment1 = analyzer.analyze_sentiment(text1)
    print(f"Text: '{text1}' -> Sentiment: {sentiment1['label']} ({sentiment1['score']:.2f})")
    assert sentiment1["label"] == "positive"
    assert not analyzer.trigger_empathy_response(sentiment1)

    print("\n--- Test Case 2: Negative Sentiment (General) ---")
    text2 = "This is a terrible situation, I'm very upset."
    sentiment2 = analyzer.analyze_sentiment(text2)
    print(f"Text: '{text2}' -> Sentiment: {sentiment2['label']} ({sentiment2['score']:.2f})")
    assert sentiment2["label"] == "negative"
    assert analyzer.trigger_empathy_response(sentiment2)

    print("\n--- Test Case 3: Panic Indicator ---")
    text3 = "I'm panicking! I can't cope with this. Please help me now!"
    sentiment3 = analyzer.analyze_sentiment(text3)
    print(f"Text: '{text3}' -> Sentiment: {sentiment3['label']} ({sentiment3['score']:.2f}), Indicators: {sentiment3['emotional_indicators']}")
    assert sentiment3["emotional_indicators"]["panic"]
    assert analyzer.trigger_empathy_response(sentiment3)

    print("\n--- Test Case 4: Depression Indicator ---")
    text4 = "It feels so hopeless, there's no point in anything anymore."
    sentiment4 = analyzer.analyze_sentiment(text4)
    print(f"Text: '{text4}' -> Sentiment: {sentiment4['label']} ({sentiment4['score']:.2f}), Indicators: {sentiment4['emotional_indicators']}")
    assert sentiment4["emotional_indicators"]["depression"]
    assert analyzer.trigger_empathy_response(sentiment4)

    print("\n--- Test Case 5: Anger Indicator (ALL CAPS) ---")
    text5 = "I AM SO MAD AT THIS SITUATION! IT'S UNBELIEVABLE!"
    sentiment5 = analyzer.analyze_sentiment(text5)
    print(f"Text: '{text5}' -> Sentiment: {sentiment5['label']} ({sentiment5['score']:.2f}), Indicators: {sentiment5['emotional_indicators']}")
    assert sentiment5["emotional_indicators"]["anger"]
    assert analyzer.trigger_empathy_response(sentiment5)

    print("\n--- Test Case 6: High Pain Intensity ---")
    text6 = "The pain is absolutely unbearable, it's excruciating!"
    sentiment6 = analyzer.analyze_sentiment(text6)
    print(f"Text: '{text6}' -> Sentiment: {sentiment6['label']} ({sentiment6['score']:.2f}), Indicators: {sentiment6['emotional_indicators']}")
    assert sentiment6["emotional_indicators"]["high_pain_intensity"]
    assert analyzer.trigger_empathy_response(sentiment6)

    print("\n--- Test Case 7: Neutral Sentiment ---")
    text7 = "The weather is quite pleasant today."
    sentiment7 = analyzer.analyze_sentiment(text7)
    print(f"Text: '{text7}' -> Sentiment: {sentiment7['label']} ({sentiment7['score']:.2f}), Indicators: {sentiment7['emotional_indicators']}")
    assert sentiment7["label"] == "neutral"
