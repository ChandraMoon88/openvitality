# src/intelligence/medical_fact_checker.py

from typing import Dict, Any, List
import asyncio
import re

# Assuming these imports will be available from other modules
# from src.intelligence.llm_interface import LLMProvider
# from src.core.knowledge_base_manager import KnowledgeBaseManager # For internal KB lookup

class MedicalFactChecker:
    """
    Verifies medical claims for accuracy and safety, aiming to prevent misinformation
    and hallucinations in AI responses.
    """
    def __init__(self, llm_provider_instance, knowledge_base_manager_instance):
        """
        Initializes the MedicalFactChecker.
        
        :param llm_provider_instance: An initialized LLMProvider instance,
                                      potentially for RAG or specialized queries.
        :param knowledge_base_manager_instance: An instance of KnowledgeBaseManager
                                                for looking up trusted medical information.
        """
        self.llm = llm_provider_instance
        self.knowledge_base = knowledge_base_manager_instance
        
        # Threshold for LLM confidence in its own fact-check, if applicable
        self.llm_confidence_threshold = 0.8
        
        print("✅ MedicalFactChecker initialized.")

    async def verify_medical_claim(self, claim: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Verifies a given medical claim against trusted sources.
        
        :param claim: The medical statement to verify.
        :param context: Optional context, such as session history or patient information.
        :return: A dictionary with verdict, evidence, and confidence.
        """
        report = {
            "claim": claim,
            "verdict": "uncertain", # safe, unsafe, uncertain
            "confidence": 0.5,
            "evidence": [],
            "reasoning": ""
        }

        # 1. Check against internal knowledge base (e.g., WHO/CDC guidelines)
        kb_evidence = await self._check_internal_knowledge_base(claim)
        if kb_evidence:
            report["evidence"].extend(kb_evidence)
            # Simple logic: if KB has clear, contradictory evidence, it's unsafe.
            # If KB directly supports, it's safe.
            if any("unsafe" in e.get("verdict", "").lower() for e in kb_evidence):
                report["verdict"] = "unsafe"
                report["confidence"] = 0.95
                report["reasoning"] = "Contradicted by internal trusted medical knowledge base."
                return report
            elif any("safe" in e.get("verdict", "").lower() for e in kb_evidence):
                report["verdict"] = "safe"
                report["confidence"] = 0.9
                report["reasoning"] = "Supported by internal trusted medical knowledge base."
                return report

        # 2. Use LLM for broader fact-checking or complex reasoning
        # This could involve RAG (Retrieval Augmented Generation) where the LLM
        # queries search engines or specialized databases.
        llm_fact_check_result = await self._llm_based_fact_check(claim, context)
        report["evidence"].extend(llm_fact_check_result["evidence"])

        if llm_fact_check_result["verdict"] != "uncertain":
            # If LLM has a strong verdict, update report
            if llm_fact_check_result["confidence"] > self.llm_confidence_threshold:
                report["verdict"] = llm_fact_check_result["verdict"]
                report["confidence"] = max(report["confidence"], llm_fact_check_result["confidence"])
                report["reasoning"] += f"\nLLM-based verification: {llm_fact_check_result['reasoning']}"
                return report
            else:
                report["reasoning"] += f"\nLLM-based verification was low confidence: {llm_fact_check_result['reasoning']}"


        # Final verdict if no strong conclusion
        if report["verdict"] == "uncertain" and not report["evidence"]:
            report["reasoning"] = "Could not find sufficient evidence in trusted sources."
        elif report["verdict"] == "uncertain":
            # If some evidence, but no clear safe/unsafe verdict
            report["reasoning"] = "Evidence found, but unable to definitively conclude safety/accuracy."

        return report

    async def _check_internal_knowledge_base(self, claim: str) -> List[Dict[str, Any]]:
        """
        Queries the internal knowledge base for facts related to the claim.
        """
        # Example: Simple keyword matching against a mock KB.
        # In reality, this would be a semantic search.
        keywords = claim.lower().split()
        evidence_list = []

        # Mock direct contradictions
        if "drink bleach" in claim.lower() or "vaccines cause autism" in claim.lower():
            evidence_list.append({
                "source": "WHO Guidelines",
                "fact": f"Statement '{claim}' is false. Such actions are harmful and ineffective.",
                "verdict": "unsafe",
                "link": "https://www.who.int/emergencies/diseases/novel-coronavirus-2019/advice-for-public"
            })
        
        # Mock positive support
        if "500mg paracetamol" in claim.lower() or "fever reduction" in claim.lower():
            evidence_list.append({
                "source": "CDC Guidelines",
                "fact": f"Paracetamol (acetaminophen) can be used for fever reduction.",
                "verdict": "safe",
                "link": "https://www.cdc.gov/flu/symptoms/cold-flu-symptoms.htm"
            })

        # Use the KnowledgeBaseManager (mocked here)
        # relevant_docs = await self.knowledge_base.search(claim, limit=3)
        # for doc in relevant_docs:
        #     evidence_list.append({
        #         "source": doc.source,
        #         "fact": doc.content,
        #         "verdict": "uncertain", # Requires further LLM interpretation
        #         "link": doc.link
        #     })
            
        return evidence_list

    async def _llm_based_fact_check(self, claim: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Uses the LLM to perform a fact-check. This could be a direct query
        or RAG-style where LLM processes retrieved documents.
        """
        # For this mock, we'll simulate an LLM's response.
        # In a real scenario, you'd construct a prompt asking the LLM to verify the claim
        # based on its internal knowledge or provided documents.
        
        # prompt_to_llm = f"Given the following medical claim: '{claim}'. Based on current medical consensus, is this claim safe and accurate? Provide a verdict (safe, unsafe, uncertain) and a brief reason."
        # llm_response = await self.llm.generate_response(prompt_to_llm, [])
        
        # Simulate LLM parsing
        llm_verdict = "uncertain"
        llm_confidence = 0.5
        llm_reasoning = "Simulated LLM response: could not definitively confirm or deny."
        llm_evidence = []

        if "aspirin for headache" in claim.lower():
            llm_verdict = "safe"
            llm_confidence = 0.85
            llm_reasoning = "Aspirin is commonly used for headache relief, but contraindications apply."
            llm_evidence.append({"source": "LLM knowledge", "fact": "Aspirin is an NSAID used for pain relief."})
        elif "quick weight loss pills" in claim.lower():
            llm_verdict = "unsafe"
            llm_confidence = 0.9
            llm_reasoning = "Many quick weight loss pills are ineffective or harmful and lack scientific backing."
            llm_evidence.append({"source": "LLM knowledge", "fact": "Rapid weight loss methods can be dangerous."})

        return {
            "verdict": llm_verdict,
            "confidence": llm_confidence,
            "reasoning": llm_reasoning,
            "evidence": llm_evidence
        }


# Example Usage
if __name__ == "__main__":
    # --- Mock Dependencies ---
    class MockLLMProvider:
        def __init__(self, config=None): pass
        async def generate_response(self, prompt: str, history: List[Dict]) -> str:
            return "simulated LLM response"
        async def count_tokens(self, text: str) -> int: return len(text.split())
        def supports_streaming(self) -> bool: return False
        def supports_multimodality(self) -> bool: return False
        def get_model_name(self) -> str: return "mock-llm-fact-checker"
    
    class MockKnowledgeBaseManager:
        async def search(self, query: str, limit: int):
            return [] # Empty for now

    # --- Initialize ---
    mock_llm = MockLLMProvider()
    mock_kb = MockKnowledgeBaseManager()
    
    fact_checker = MedicalFactChecker(mock_llm, mock_kb)

    # --- Test 1: Safe claim ---
    print("\n--- Test 1: Safe claim ---")
    claim_safe = "Taking 500mg paracetamol can help reduce fever."
    report_safe = asyncio.run(fact_checker.verify_medical_claim(claim_safe))
    print(f"Report for '{claim_safe}': {report_safe}")

    # --- Test 2: Unsafe claim (direct contradiction in mock KB) ---
    print("\n--- Test 2: Unsafe claim ---")
    claim_unsafe = "It is safe to drink bleach to cure viral infections."
    report_unsafe = asyncio.run(fact_checker.verify_medical_claim(claim_unsafe))
    print(f"Report for '{claim_unsafe}': {report_unsafe}")

    # --- Test 3: Uncertain claim (not in mock KB, LLM has no strong opinion) ---
    print("\n--- Test 3: Uncertain claim ---")
    claim_uncertain = "Eating raw garlic can prevent all types of cancer."
    report_uncertain = asyncio.run(fact_checker.verify_medical_claim(claim_uncertain))
    print(f"Report for '{claim_uncertain}': {report_uncertain}")

    # --- Test 4: LLM-influenced safe claim ---
    print("\n--- Test 4: LLM-influenced safe claim ---")
    claim_llm_safe = "Aspirin can be used for headache relief."
    report_llm_safe = asyncio.run(fact_checker.verify_medical_claim(claim_llm_safe))
    print(f"Report for '{claim_llm_safe}': {report_llm_safe}")

    # --- Test 5: LLM-influenced unsafe claim ---
    print("\n--- Test 5: LLM-influenced unsafe claim ---")
    claim_llm_unsafe = "Quick weight loss pills are a healthy way to lose weight."
    report_llm_unsafe = asyncio.run(fact_checker.verify_medical_claim(claim_llm_unsafe))
    print(f"Report for '{claim_llm_unsafe}': {report_llm_unsafe}")
