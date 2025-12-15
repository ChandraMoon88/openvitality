import logging
from typing import List, Dict, Any, Optional
import asyncio
import numpy as np

try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("Sentence-transformers library not installed. Cross-encoder reranking functionality will be unavailable.")

logger = logging.getLogger(__name__)

class RetrievalRanker:
    """
    Improves search quality by re-ranking initially retrieved document chunks
    based on their relevance to the query. Uses a cross-encoder model for this task.
    """
    def __init__(self,
                 cross_encoder_model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        """
        Initializes the RetrievalRanker with a specified cross-encoder model.

        Args:
            cross_encoder_model_name (str): The name of the Hugging Face cross-encoder model to use.
                                            (e.g., 'cross-encoder/ms-marco-MiniLM-L-6-v2',
                                            'cross-encoder/nli-deberta-base').
        """
        self.cross_encoder = None
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.error("Sentence-transformers is not available. Reranking will be disabled.")
            return

        try:
            self.cross_encoder = CrossEncoder(cross_encoder_model_name)
            logger.info(f"Cross-encoder model '{cross_encoder_model_name}' loaded for reranking.")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model '{cross_encoder_model_name}': {e}. Reranking will be disabled.")
            self.cross_encoder = None

    async def rerank(self, query: str, retrieved_chunks: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Re-ranks a list of retrieved document chunks based on their relevance to the query.

        Args:
            query (str): The original query string.
            retrieved_chunks (List[Dict[str, Any]]): A list of dictionaries, where each dict
                                                      represents a retrieved document chunk.
                                                      Each dict *must* contain a 'text' key.
            top_k (int): The number of top-ranked chunks to return.

        Returns:
            List[Dict[str, Any]]: A new list of chunks, sorted by relevance score in descending order,
                                  with only the top_k chunks included. Each dict will have an added 'relevance_score'.
        """
        if not self.cross_encoder:
            logger.warning("Cross-encoder not loaded. Returning original chunks without reranking.")
            return retrieved_chunks[:top_k]

        if not retrieved_chunks:
            return []

        # Prepare sentence pairs for the cross-encoder
        # Each pair is (query, document_text)
        sentence_pairs = [(query, chunk["text"]) for chunk in retrieved_chunks]

        try:
            # Score all pairs. The score indicates relevance of the document to the query.
            # Scores are typically logits, higher means more relevant.
            scores = self.cross_encoder.predict(sentence_pairs)
            
            # Combine chunks with their new scores
            scored_chunks = []
            for i, chunk in enumerate(retrieved_chunks):
                chunk_copy = chunk.copy()
                chunk_copy["relevance_score"] = scores[i].item() # .item() to get scalar from numpy array
                scored_chunks.append(chunk_copy)
            
            # Sort by relevance score in descending order
            scored_chunks.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            logger.info(f"Reranked {len(retrieved_chunks)} chunks, returning top {top_k}.")
            return scored_chunks[:top_k]

        except Exception as e:
            logger.error(f"Error during reranking with cross-encoder: {e}. Returning original top {top_k} chunks.")
            return retrieved_chunks[:top_k]

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("Sentence-transformers not installed. Skipping example.")
    else:
        ranker = RetrievalRanker()

        async def run_rerank_tests():
            query = "What are the common symptoms of a heart attack?"
            
            # Simulate initial retrieved chunks (e.g., from a vector DB search)
            # These are intentionally ordered to be re-ranked
            initial_chunks = [
                {"text": "Shortness of breath, chest pain, and discomfort in other areas of the upper body are common signs of a heart attack. Some people also experience nausea or lightheadedness.", "metadata": {"source": "AHA", "page": "5"}},
                {"text": "A heart attack occurs when the flow of blood to the heart is blocked, most often by a buildup of fat, cholesterol, and other substances, which form plaques in the arteries that feed the heart.", "metadata": {"source": "Mayo Clinic", "page": "10"}},
                {"text": "Symptoms of a common cold include runny nose, sore throat, and sneezing. These are typically mild.", "metadata": {"source": "CDC", "page": "20"}}, # Irrelevant chunk
                {"text": "Crushing chest pain and discomfort radiating to the left arm are classic symptoms.", "metadata": {"source": "WebMD", "page": "8"}},
                {"text": "Cardiac arrest is when the heart suddenly stops beating. It is not the same as a heart attack.", "metadata": {"source": "NHLBI", "page": "15"}},
            ]

            print("\n--- Initial Retrieved Chunks ---")
            for i, chunk in enumerate(initial_chunks):
                print(f"{i+1}. {chunk['text'][:70]}...")

            print("\n--- Reranking Chunks ---")
            reranked_chunks = await ranker.rerank(query, initial_chunks, top_k=3)
            
            print("\n--- Top 3 Reranked Chunks ---")
            for i, chunk in enumerate(reranked_chunks):
                print(f"{i+1}. Score: {chunk['relevance_score']:.4f}, Text: '{chunk['text'][:70]}'")
            
            # Assertions: the most relevant chunks should be at the top
            assert len(reranked_chunks) == 3
            assert "Shortness of breath, chest pain" in reranked_chunks[0]["text"]
            assert "Crushing chest pain and discomfort" in reranked_chunks[1]["text"]
            assert "A heart attack occurs when the flow of blood" in reranked_chunks[2]["text"]
            # The cold symptoms chunk should be filtered out or ranked very low
            
            print("\n--- Test with Empty Chunks ---")
            empty_rerank = await ranker.rerank(query, [], top_k=5)
            print(f"Reranking empty list: {empty_rerank}")
            assert len(empty_rerank) == 0

        import asyncio
        asyncio.run(run_rerank_tests())

    