import logging
from typing import List, Optional, Union
from functools import lru_cache

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logging.warning("Sentence-transformers library not installed. Embedding functionality will be limited.")

# Assuming a global config for embedding model registration
from src.knowledge import register_embedding_model

logger = logging.getLogger(__name__)

class HFEmbeddingModel:
    """
    Generates text embeddings using a Hugging Face SentenceTransformer model.
    This class is intended as a FREE alternative to OpenAI embeddings,
    as specified in the documentation (despite the misleading filename).

    Model: 'sentence-transformers/all-MiniLM-L6-v2' (384-dimensional, CPU-friendly)
    Supports batch processing and includes caching for efficiency.
    """
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", cache_size: int = 1000):
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("Sentence-transformers library not found. Please install it with `pip install sentence-transformers`.")
        
        self.model_name = model_name
        try:
            # Setting device='cpu' explicitly to ensure CPU-friendliness as per requirement
            self.model = SentenceTransformer(self.model_name, device='cpu')
            logger.info(f"Hugging Face SentenceTransformer model '{self.model_name}' loaded successfully on CPU.")
            
            # Cache the embedding generation method
            # lru_cache works on instances, so we bind it to the method
            self._get_embedding_uncached = lru_cache(maxsize=cache_size)(self.__get_embedding_uncached)

        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model '{self.model_name}': {e}.")
            self.model = None
            raise

    def __get_embedding_uncached(self, text: str) -> List[float]:
        """Internal method for generating a single embedding without caching."""
        if not self.model:
            raise RuntimeError("Embedding model is not loaded.")
        
        # model.encode returns a numpy array, convert to list for consistency
        embedding = self.model.encode(text)
        return embedding.tolist()

    async def get_embedding(self, text: str) -> List[float]:
        """
        Generates an embedding for a single piece of text.
        Uses caching to return pre-computed embeddings for duplicate texts.
        """
        if not text:
            return []
        # Await the cached function. lru_cache works on the result of the function,
        # so if the function itself is async, we still need to await.
        # However, lru_cache doesn't directly support async methods.
        # For simplicity, we'll make the underlying call synchronous and wrap it for async compatibility.
        # In a real heavy-load scenario, this might need an executor.
        return self._get_embedding_uncached(text)

    async def get_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generates embeddings for a list of texts in batches.
        Applies caching for individual texts within the batch.
        """
        if not self.model:
            raise RuntimeError("Embedding model is not loaded.")
        if not texts:
            return []
        
        embeddings_list: List[List[float]] = []
        texts_to_process: List[str] = []
        cached_embeddings: Dict[str, List[float]] = {}
        
        # Check cache for each text
        for text in texts:
            cached_embedding = self._get_embedding_uncached.cache_get(text) # Direct access to lru_cache's internal get
            if cached_embedding is not None:
                cached_embeddings[text] = cached_embedding
            else:
                texts_to_process.append(text)
        
        # Process uncached texts in batches
        if texts_to_process:
            logger.debug(f"Generating embeddings for {len(texts_to_process)} uncached texts in batches.")
            # self.model.encode handles batching internally if given a list
            new_embeddings_np = self.model.encode(texts_to_process, batch_size=batch_size, show_progress_bar=False)
            
            for i, text in enumerate(texts_to_process):
                embedding = new_embeddings_np[i].tolist()
                embeddings_list.append(embedding)
                self._get_embedding_uncached.cache_set(text, embedding) # Manually update cache
        
        # Combine cached and newly computed embeddings, maintaining original order
        final_embeddings = []
        for text in texts:
            if text in cached_embeddings:
                final_embeddings.append(cached_embeddings[text])
            else:
                # This path should ideally not be hit if cache_set worked correctly,
                # but as a fallback, recompute (will be slow if many misses)
                final_embeddings.append(self._get_embedding_uncached(text))

        return final_embeddings

# Register this embedding model with the knowledge module's registry
register_embedding_model("huggingface_minilm", HFEmbeddingModel)

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        # Get an instance of the embedding model via the registry
        embedding_model = HFEmbeddingModel() # Directly instantiate for example
        # or from registry: embedding_model = get_embedding_model("huggingface_minilm")

        async def run_embedding_tests():
            print("\n--- Test 1: Single Embedding ---")
            text1 = "What is the dosage for amoxicillin?"
            embedding1 = await embedding_model.get_embedding(text1)
            print(f"Embedding for '{text1}' (first 5 dims): {embedding1[:5]}...")
            print(f"Embedding dimension: {len(embedding1)}")
            assert len(embedding1) == 384 # all-MiniLM-L6-v2 outputs 384-dimensional embeddings

            print("\n--- Test 2: Batched Embeddings ---")
            texts_batch = [
                "Symptoms of the common cold.",
                "How to treat a fever?",
                "What is the dosage for amoxicillin?", # Duplicate to test caching
                "Best practices for diabetes management."
            ]
            embeddings_batch = await embedding_model.get_embeddings(texts_batch, batch_size=2)
            for i, text in enumerate(texts_batch):
                print(f"Embedding for '{text}' (first 5 dims): {embeddings_batch[i][:5]}...")
            print(f"Total embeddings generated: {len(embeddings_batch)}")
            assert len(embeddings_batch) == len(texts_batch)
            assert len(embeddings_batch[0]) == 384

            print("\n--- Test 3: Caching Check (second call should be faster/hit cache) ---")
            start_time = datetime.datetime.now()
            embedding_cached = await embedding_model.get_embedding(text1)
            end_time = datetime.datetime.now()
            print(f"Time for cached embedding: {(end_time - start_time).total_seconds():.4f}s")
            
            # Clear cache for manual check
            # embedding_model._get_embedding_uncached.cache_clear()
            # start_time = datetime.datetime.now()
            # embedding_uncached = await embedding_model.get_embedding(text1)
            # end_time = datetime.datetime.now()
            # print(f"Time for uncached embedding: {(end_time - start_time).total_seconds():.4f}s")

        import asyncio
        asyncio.run(run_embedding_tests())

    except ImportError as e:
        print(f"Error: {e}. Please install sentence-transformers to run the example.")
