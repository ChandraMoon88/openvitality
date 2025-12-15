import re
import logging
from typing import List, Dict, Any, Optional

try:
    import spacy
    # You would typically install scispacy and download models like:
    # pip install scispacy
    # python -m spacy download en_core_sci_lg
    # python -m spacy download en_ner_bc5cdr_md
    # python -m spacy download en_ner_bionlp13cg_md
    # python -m spacy download en_ner_craft_md
    # python -m spacy download en_ner_jnlpba_md
    # python -m spacy download en_ner_linnaeus_md
    # python -m spacy download en_ner_ncbi_disease_md
    # python -m spacy download en_ner_species_md
except ImportError:
    spacy = None
    logging.warning("spaCy or scispacy not installed. Medical entity extraction will be limited to regex-based methods.")

logger = logging.getLogger(__name__)

class MedicalEntityExtractor:
    """
    Finds and extracts medical terms, durations, and dosages from text.
    Leverages spaCy/scispaCy for advanced NER and regex for structured patterns.
    """
    def __init__(self, spacy_model_name: str = "en_core_sci_lg"):
        self.nlp = None
        if spacy:
            try:
                self.nlp = spacy.load(spacy_model_name)
                logger.info(f"spaCy model '{spacy_model_name}' loaded successfully for medical entity extraction.")
            except OSError:
                logger.warning(f"spaCy model '{spacy_model_name}' not found. Attempting to load 'en_core_web_sm' as fallback.")
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("Loaded 'en_core_web_sm' as fallback spaCy model.")
                except OSError:
                    logger.error("Neither specified spaCy model nor 'en_core_web_sm' could be loaded. spaCy NER disabled.")
                    self.nlp = None
        else:
            logger.warning("spaCy is not installed. Advanced NER will be unavailable.")

        # Regex patterns for common entities not always covered by general NER models
        self.duration_patterns = [
            re.compile(r"(\d+)\s+(day|week|month|year)s?", re.IGNORECASE),
            re.compile(r"(a few|several)\s+(day|week|month|year)s?", re.IGNORECASE),
            re.compile(r"(yesterday|today|tomorrow)", re.IGNORECASE)
        ]
        self.dosage_patterns = [
            re.compile(r"(\d+\.?\d*)\s*(mg|g|mcg|unit)s?", re.IGNORECASE),
            re.compile(r"(one|two|three|four|five|six|seven|eight|nine|ten)\s+(tablet|pill|capsule)s?", re.IGNORECASE),
            re.compile(r"(\d+\.?\d*)\s*(tablet|pill|capsule)s?", re.IGNORECASE),
            re.compile(r"(\d+\.?\d*)\s*(ml|cc|teaspoon|tablespoon)s?", re.IGNORECASE)
        ]

        # Simple keyword lists for symptoms, body parts, diseases if no NER model is loaded
        self.symptom_keywords = ["fever", "cough", "pain", "headache", "sore throat", "nausea", "vomiting", "diarrhea", "rash", "fatigue", "dizziness"]
        self.body_part_keywords = ["head", "chest", "stomach", "leg", "arm", "throat", "eye", "ear", "nose", "heart", "lung", "brain"]
        self.disease_keywords = ["diabetes", "hypertension", "asthma", "cold", "flu", "cancer", "malaria"]


    def extract_entities(self, text: str, lang_code: str = "en") -> List[Dict[str, Any]]:
        """
        Extracts medical and related entities from the given text.

        Args:
            text (str): The input text.
            lang_code (str): The language code of the text (e.g., "en").

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing an extracted entity.
                                  Each dict contains 'text', 'type', 'start_char', 'end_char',
                                  and optionally 'normalized_value', 'code'.
        """
        entities = []
        if not text:
            return entities

        # 1. spaCy/scispaCy NER
        if self.nlp and lang_code == "en": # scispaCy models are typically English-specific
            doc = self.nlp(text)
            for ent in doc.ents:
                entities.append({
                    "text": ent.text,
                    "type": ent.label_.upper(), # e.g., 'DISEASE', 'CHEMICAL', 'SYMPTOM'
                    "start_char": ent.start_char,
                    "end_char": ent.end_char,
                    "source": "spacy_ner"
                })
        
        # 2. Regex-based extraction (can complement or act as fallback)
        entities.extend(self._extract_regex_entities(text))

        # 3. Keyword-based extraction (fallback if no NER model)
        if not self.nlp or lang_code != "en":
            entities.extend(self._extract_keyword_entities(text))

        # 4. Normalization and Brand Mapping (placeholder)
        # Iterate through entities and apply normalization/mapping logic
        # For example: "Tylenol" -> "Acetaminophen" (CHEMICAL)
        # "Diabetes Mellitus" -> "Diabetes" (DISEASE)
        for entity in entities:
            entity["normalized_value"] = self._normalize_entity(entity["text"], entity["type"])
            # entity["code"] = self._map_to_standard_code(entity["normalized_value"], entity["type"])
            # entity["brand_mapped"] = self._map_brand_to_generic(entity["text"], entity["type"])

        logger.debug(f"Extracted entities for '{text}': {entities}")
        return entities

    def _extract_regex_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extracts entities using regex patterns."""
        regex_entities = []

        # Durations
        for pattern in self.duration_patterns:
            for match in pattern.finditer(text):
                regex_entities.append({
                    "text": match.group(0),
                    "type": "DURATION",
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "source": "regex"
                })
        
        # Dosages
        for pattern in self.dosage_patterns:
            for match in pattern.finditer(text):
                regex_entities.append({
                    "text": match.group(0),
                    "type": "DOSAGE",
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "source": "regex"
                })
        return regex_entities

    def _extract_keyword_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extracts entities based on simple keyword matching.
        This is a basic fallback and can produce many false positives.
        """
        keyword_entities = []
        text_lower = text.lower()

        # Symptoms
        for keyword in self.symptom_keywords:
            if keyword in text_lower:
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    keyword_entities.append({
                        "text": text[match.start():match.end()],
                        "type": "SYMPTOM",
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "source": "keyword"
                    })
        # Body Parts
        for keyword in self.body_part_keywords:
            if keyword in text_lower:
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    keyword_entities.append({
                        "text": text[match.start():match.end()],
                        "type": "BODY_PART",
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "source": "keyword"
                    })
        # Diseases
        for keyword in self.disease_keywords:
            if keyword in text_lower:
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    keyword_entities.append({
                        "text": text[match.start():match.end()],
                        "type": "DISEASE",
                        "start_char": match.start(),
                        "end_char": match.end(),
                        "source": "keyword"
                    })
        return keyword_entities


    def _normalize_entity(self, entity_text: str, entity_type: str) -> str:
        """
        Placeholder for normalizing entity text (e.g., "fevers" -> "fever").
        """
        if entity_type == "SYMPTOM" and entity_text.lower().endswith('s') and len(entity_text) > 1:
            return entity_text[:-1] # Simple plural removal
        return entity_text

    def _map_to_standard_code(self, normalized_value: str, entity_type: str) -> Optional[str]:
        """
        Placeholder for mapping entities to standard medical codes (UMLS, SNOMED).
        This would typically involve a lookup in a medical knowledge graph or database.
        """
        # Example: if entity_type == "DISEASE" and normalized_value == "Diabetes": return "ICD10:E11.9"
        return None

    def _map_brand_to_generic(self, brand_name: str, entity_type: str) -> Optional[str]:
        """
        Placeholder for mapping drug brand names to generic names.
        """
        # Example: if entity_type == "CHEMICAL" and brand_name.lower() == "tylenol": return "Acetaminophen"
        return None


# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # To run this example fully, ensure scispacy is installed and models are downloaded:
    # pip install scispacy
    # python -m spacy download en_core_sci_lg
    # python -m spacy download en_ner_bc5cdr_md

    # Try with a scispaCy model first, fallback to general if not available
    try:
        extractor = MedicalEntityExtractor(spacy_model_name="en_ner_bc5cdr_md")
    except Exception:
        extractor = MedicalEntityExtractor(spacy_model_name="en_core_web_sm")
        logging.warning("Using generic spaCy model for example due to scispaCy issues.")

    print("\n--- Test Case 1: Symptoms and Duration ---")
    text1 = "I have had a severe headache and fever for 3 days."
    entities1 = extractor.extract_entities(text1)
    for ent in entities1:
        print(f"Text: '{ent['text']}', Type: {ent['type']}, Norm: {ent.get('normalized_value')}")

    print("\n--- Test Case 2: Disease and Dosage ---")
    text2 = "My blood sugar is high. I take 500mg of Metformin daily for my Diabetes."
    entities2 = extractor.extract_entities(text2)
    for ent in entities2:
        print(f"Text: '{ent['text']}', Type: {ent['type']}, Norm: {ent.get('normalized_value')}")

    print("\n--- Test Case 3: Body Part ---")
    text3 = "I have pain in my left arm and a sore throat."
    entities3 = extractor.extract_entities(text3)
    for ent in entities3:
        print(f"Text: '{ent['text']}', Type: {ent['type']}, Norm: {ent.get('normalized_value')}")

    print("\n--- Test Case 4: Advanced Duration ---")
    text4 = "The flu has lasted for two weeks and a few days."
    entities4 = extractor.extract_entities(text4)
    for ent in entities4:
        print(f"Text: '{ent['text']}', Type: {ent['type']}, Norm: {ent.get('normalized_value')}")

    print("\n--- Test Case 5: Without spaCy (keyword/regex fallback) ---")
    # Temporarily disable spaCy for this test
    old_nlp = extractor.nlp
    extractor.nlp = None
    text5 = "I have a cough and my stomach hurts for a week. I took two pills."
    entities5 = extractor.extract_entities(text5)
    for ent in entities5:
        print(f"Text: '{ent['text']}', Type: {ent['type']}, Norm: {ent.get('normalized_value')}")
    extractor.nlp = old_nlp # Restore spaCy
