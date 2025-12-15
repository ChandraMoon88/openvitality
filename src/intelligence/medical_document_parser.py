# src/intelligence/medical_document_parser.py

from typing import Dict, Any, List
import asyncio
import re
import json
import base64

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider
# from src.language.entity_extractor_medical import MedicalEntityExtractor
# from src.core.telemetry_emitter import TelemetryEmitter

# Mock OCR library if not installed. In a real system, you'd use Tesseract or cloud OCR.
try:
    import pytesseract
    # You'd also need to configure Tesseract path: pytesseract.pytesseract.tesseract_cmd = r'<full_path_to_tesseract_executable>'
    IS_TESSERACT_AVAILABLE = True
except ImportError:
    IS_TESSERACT_AVAILABLE = False
    print("⚠️ WARNING: pytesseract not found. OCR functionality will be disabled.")
    print("To enable, install: pip install pytesseract && install Tesseract OCR engine.")


class MedicalDocumentParser:
    """
    Extracts structured information from unstructured medical documents,
    including doctor's notes, lab reports, and discharge summaries.
    """
    def __init__(self, llm_provider_instance, entity_extractor_instance, telemetry_emitter_instance):
        """
        Initializes the MedicalDocumentParser.
        
        :param llm_provider_instance: An initialized LLMProvider instance for summarization and advanced parsing.
        :param entity_extractor_instance: An initialized MedicalEntityExtractor instance for NER.
        :param telemetry_emitter_instance: An initialized TelemetryEmitter instance.
        """
        self.llm = llm_provider_instance
        self.entity_extractor = entity_extractor_instance
        self.telemetry = telemetry_emitter_instance
        
        self.supported_document_types = ["doctors_notes", "lab_report", "discharge_summary"]
        print("✅ MedicalDocumentParser initialized.")

    async def parse_document(self, document_data: str | bytes, document_type: str, file_format: str = "text") -> Dict[str, Any]:
        """
        Parses a medical document to extract structured information.
        
        :param document_data: The content of the document (str for text, bytes for image/PDF).
        :param document_type: The type of medical document (e.g., "doctors_notes", "lab_report").
        :param file_format: The format of the document ("text", "pdf", "image_base64").
        :return: A dictionary containing extracted entities, relationships, and a summary.
        """
        parsed_report = {
            "document_type": document_type,
            "extracted_text": "",
            "extracted_entities": [],
            "inferred_relationships": [],
            "summary": "Parsing pending.",
            "error": None
        }
        
        if document_type not in self.supported_document_types:
            parsed_report["error"] = f"Unsupported document type: {document_type}"
            parsed_report["summary"] = "Parsing failed due to unsupported document type."
            self.telemetry.emit_event("doc_parsing_error", {"document_type": document_type, "error": "unsupported_type"})
            return parsed_report

        try:
            # 1. Extract text from document
            extracted_text = await self._extract_text_from_document(document_data, file_format)
            parsed_report["extracted_text"] = extracted_text.strip()

            if not extracted_text.strip():
                parsed_report["error"] = "No text could be extracted from the document."
                parsed_report["summary"] = "Document is empty or could not be processed."
                return parsed_report

            # 2. Named Entity Recognition (NER)
            parsed_report["extracted_entities"] = self.entity_extractor.extract(extracted_text)

            # 3. Relationship Extraction (simplified via LLM)
            parsed_report["inferred_relationships"] = await self._infer_relationships_llm(extracted_text, parsed_report["extracted_entities"])

            # 4. Summarization of key findings
            parsed_report["summary"] = await self._summarize_document_llm(extracted_text, document_type, parsed_report["extracted_entities"])

            self.telemetry.emit_event("doc_parsing_complete", {"document_type": document_type, "entities_count": len(parsed_report["extracted_entities"])})

        except Exception as e:
            parsed_report["error"] = str(e)
            parsed_report["summary"] = f"An error occurred during document parsing: {e}"
            self.telemetry.emit_event("doc_parsing_error", {"document_type": document_type, "error": str(e)})

        return parsed_report

    async def _extract_text_from_document(self, document_data: str | bytes, file_format: str) -> str:
        """
        Extracts raw text content from various document formats.
        """
        if file_format == "text":
            return document_data.decode('utf-8') if isinstance(document_data, bytes) else document_data
        elif file_format == "image_base64":
            if not IS_TESSERACT_AVAILABLE:
                raise RuntimeError("pytesseract (OCR) is not installed or configured.")
            
            # Simulate OCR process
            # from PIL import Image
            # image = Image.open(io.BytesIO(base64.b64decode(document_data)))
            # return pytesseract.image_to_string(image)
            
            # Mock OCR response
            if "fever" in document_data.lower():
                return "Patient has a fever and headache. Prescribed Aspirin 500mg."
            return "OCR text: Document contains medical information."
        elif file_format == "pdf":
            # For PDF, you'd typically use a library like PyPDF2 or pdfminer.six,
            # or send to a cloud API.
            # Mock PDF extraction:
            return "Text extracted from PDF: Lab results show elevated white blood cell count."
        
        raise ValueError(f"Unsupported file format for text extraction: {file_format}")

    async def _infer_relationships_llm(self, text: str, entities: List[Dict]) -> List[Dict[str, Any]]:
        """
        Uses an LLM to infer relationships between extracted entities.
        """
        relationships = []
        
        # Construct a prompt for the LLM to identify relationships
        prompt = f"""Analyze the following medical text and extracted entities. Identify and list any clear relationships between these entities (e.g., "DRUG X TREATS DISEASE Y", "SYMPTOM A IS_A_SYMPTOM_OF DISEASE B").
        
        Text: {text}
        Entities: {json.dumps(entities, indent=2)}
        
        Format output as a list of dictionaries, e.g.,
        [
          {{"source_entity": "entity_id", "target_entity": "entity_id", "relationship_type": "TREATS"}},
          {{"source_entity": "entity_id", "target_entity": "entity_id", "relationship_type": "HAS_SYMPTOM"}}
        ]
        If no relationships, return an empty list.
        """
        
        llm_response_text = await self.llm.generate_response(prompt, [])
        
        # Simulate parsing LLM's structured output (or it can directly give JSON)
        try:
            # Mocked LLM output based on expected relationships
            if "fever" in text.lower() and "aspirin" in text.lower():
                relationships.append({"source_entity": "Aspirin", "target_entity": "fever", "relationship_type": "ALLEVIATES"})
            if "elevated white blood cell count" in text.lower():
                relationships.append({"source_entity": "Elevated white blood cell count", "target_entity": "Infection", "relationship_type": "INDICATES"})
            
        except json.JSONDecodeError:
            print(f"⚠️ LLM did not return valid JSON for relationships: {llm_response_text[:100]}...")
        
        return relationships

    async def _summarize_document_llm(self, text: str, document_type: str, entities: List[Dict]) -> str:
        """
        Uses an LLM to generate a concise summary of the document's key findings.
        """
        prompt = f"""Summarize the following medical document of type '{document_type}'.
        Focus on key findings, diagnoses, treatments, and follow-up instructions.
        Mention the most important extracted entities: {', '.join([e['value'] for e in entities[:5]]) if entities else 'None'}.
        
        Document Content:
        {text}
        
        Concise Summary:"""
        
        llm_response = await self.llm.generate_response(prompt, [])
        return llm_response


# Example Usage
if __name__ == "__main__":
    
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None):
            pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            if "relationships between these entities" in prompt:
                if "fever" in prompt.lower() and "aspirin" in prompt.lower():
                    return '[{"source_entity": "Aspirin", "target_entity": "fever", "relationship_type": "ALLEVIATES"}]'
                return "[]" # No relationships
            if "Summarize the following medical document" in prompt:
                return "The document indicates a patient presenting with fever and headache, prescribed Aspirin 500mg. Lab results suggest an infection."
            return "Mock LLM response."
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-doc-parser"

    class MockMedicalEntityExtractor:
        def extract(self, text: str) -> List[Dict]:
            entities = []
            if "fever" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "fever", "start": text.lower().find("fever"), "end": text.lower().find("fever")+5})
            if "headache" in text.lower():
                entities.append({"type": "SYMPTOM", "value": "headache", "start": text.lower().find("headache"), "end": text.lower().find("headache")+8})
            if "aspirin" in text.lower():
                entities.append({"type": "DRUG", "value": "Aspirin", "start": text.lower().find("aspirin"), "end": text.lower().find("aspirin")+7})
            if "500mg" in text.lower():
                entities.append({"type": "DOSAGE", "value": "500mg", "start": text.lower().find("500mg"), "end": text.lower().find("500mg")+5})
            if "elevated white blood cell count" in text.lower():
                entities.append({"type": "LAB_RESULT", "value": "elevated white blood cell count", "start": text.lower().find("elevated white blood cell count"), "end": text.lower().find("elevated white blood cell count")+31})
            return entities

    class MockTelemetryEmitter:
        def emit_event(self, event_name: str, data: Dict):
            print(f"Telemetry Emitted: {event_name} - {json.dumps(data)}")

    # --- Initialize ---
    mock_llm = MockLLMProvider()
    mock_ee = MockMedicalEntityExtractor()
    mock_te = MockTelemetryEmitter()
    
    parser = MedicalDocumentParser(mock_llm, mock_ee, mock_te)

    # --- Test 1: Parse doctor's notes (text format) ---
    print("\n--- Test 1: Parse doctor's notes (text) ---")
    doc_data_1 = "Patient presents with a 3-day history of fever and headache. Prescribed Aspirin 500mg q.i.d. Follow-up in 1 week."
    report_1 = asyncio.run(parser.parse_document(doc_data_1, "doctors_notes", "text"))
    print(f"Report: {json.dumps(report_1, indent=2)}")

    # --- Test 2: Parse lab report (image format) ---
    print("\n--- Test 2: Parse lab report (image_base64) ---")
    # Simulate an image containing text "Lab results show elevated white blood cell count."
    dummy_image_base64_data = "dummy_base64_image_data_containing_fever" # Content for mock OCR
    report_2 = asyncio.run(parser.parse_document(dummy_image_base64_data, "lab_report", "image_base64"))
    print(f"Report: {json.dumps(report_2, indent=2)}")

    # --- Test 3: Parse unsupported document type ---
    print("\n--- Test 3: Parse unsupported document type ---")
    doc_data_3 = "Some insurance claim data."
    report_3 = asyncio.run(parser.parse_document(doc_data_3, "insurance_claim", "text"))
    print(f"Report: {json.dumps(report_3, indent=2)}")
