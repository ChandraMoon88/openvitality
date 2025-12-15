import logging
import os
from typing import List, Dict, Any, Optional, Tuple

try:
    from pinecone import Pinecone, Index
    PINECONE_AVAILABLE = True
except ImportError:
    Pinecone = None
    Index = None
    PINECONE_AVAILABLE = False
    logging.warning("Pinecone client library not installed. Pinecone vector database functionality will be unavailable.")

logger = logging.getLogger(__name__)

class PineconeDBClient:
    """
    A client for interacting with a Pinecone vector database.
    Manages connections, upserts documents, and performs similarity searches.
    """
    def __init__(self, api_key: Optional[str] = None, environment: Optional[str] = None):
        if not PINECONE_AVAILABLE:
            raise ImportError("Pinecone client library not found. Please install it with `pip install pinecone-client`.")
        
        self.api_key = api_key if api_key else os.getenv("PINECONE_API_KEY")
        self.environment = environment if environment else os.getenv("PINECONE_ENVIRONMENT")

        if not self.api_key or not self.environment:
            raise ValueError("Pinecone API key and environment must be provided or set as environment variables.")
        
        try:
            self.pinecone = Pinecone(api_key=self.api_key, environment=self.environment)
            self.indexes: Dict[str, Index] = {}
            logger.info(f"PineconeDBClient initialized for environment: {self.environment}")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone client: {e}")
            raise

    def get_or_create_index(
                            self,
                            index_name: str,
                            dimension: int,
                            metric: str = "cosine") -> Index:
        """
        Retrieves an existing index or creates a new one.

        Args:
            index_name (str): The name of the index.
            dimension (int): The dimensionality of the vectors in the index.
            metric (str): The distance metric to use (e.g., "cosine", "euclidean").

        Returns:
            pinecone.Index: The Pinecone Index object.
        """
        if index_name not in self.indexes:
            if index_name not in self.pinecone.list_indexes():
                logger.info(f"Creating new Pinecone index: '{index_name}' (dimension={dimension}, metric={metric})")
                self.pinecone.create_index(name=index_name, dimension=dimension, metric=metric)
            
            self.indexes[index_name] = self.pinecone.Index(index_name)
            logger.info(f"Pinecone index '{index_name}' ready.")
        return self.indexes[index_name]

    def upsert_documents(
                         self,
                         index_name: str,
                         vectors: List[Tuple[str, List[float], Dict[str, Any]]],
                         batch_size: int = 100):
        """
        Upserts (inserts or updates) documents to a specified index.

        Args:
            index_name (str): The name of the index to upsert to.
            vectors (List[Tuple[str, List[float], Dict[str, Any]]]): A list of tuples,
                                                                      each containing (id, embedding, metadata).
            batch_size (int): Number of vectors to upsert in a single batch.
        """
        index = self.indexes.get(index_name)
        if not index:
            raise ValueError(f"Index '{index_name}' not found. Please get_or_create_index first.")

        # Pinecone upsert method expects a list of (id, vector, metadata) tuples
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            index.upsert(vectors=batch)
            logger.debug(f"Upserted batch of {len(batch)} vectors to index '{index_name}'.")
        
        logger.info(f"Upserted {len(vectors)} documents to index '{index_name}'.")

    async def search(
                     self,
                     query_embedding: List[float],
                     index_name: str,
                     top_k: int = 5,
                     filter_clause: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Performs a similarity search within a specified index.

        Args:
            query_embedding (List[float]): The embedding of the query.
            index_name (str): The name of the index to search in.
            top_k (int): The number of top results to retrieve.
            filter_clause (Optional[Dict[str, Any]]): A dictionary to filter results by metadata.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a retrieved result.
                                  Each dict contains 'id', 'score', 'values' (embedding), 'metadata'.
        """
        index = self.indexes.get(index_name)
        if not index:
            raise ValueError(f"Index '{index_name}' not found. Please get_or_create_index first.")
        
        results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_values=False, # We usually don't need the embedding values back
            include_metadata=True,
            filter=filter_clause
        )
        
        formatted_results = []
        if results and results.matches:
            for match in results.matches:
                # Assuming the text content is stored in metadata under a 'text' key
                formatted_results.append({
                    "id": match.id,
                    "score": match.score,
                    "text": match.metadata.get("text", ""),
                    "metadata": match.metadata
                })
        
        logger.info(f"Searched index '{index_name}', retrieved {len(formatted_results)} results.")
        return formatted_results

    def delete_documents(self, index_name: str, ids: Optional[List[str]] = None, filter_clause: Optional[Dict[str, Any]] = None):
        """
        Deletes documents from an index by ID or metadata filter.
        """
        index = self.indexes.get(index_name)
        if not index:
            raise ValueError(f"Index '{index_name}' not found. Please get_or_create_index first.")
        
        index.delete(ids=ids, filter=filter_clause)
        logger.info(f"Deleted documents from index '{index_name}'. IDs: {ids}, Filter: {filter_clause}")

    def list_indexes(self) -> List[str]:
        """Lists all indexes in the Pinecone environment."""
        return self.pinecone.list_indexes()

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not PINECONE_AVAILABLE:
        print("Pinecone client not installed. Skipping example.")
    else:
        # Mock environment variables for Pinecone
        os.environ["PINECONE_API_KEY"] = "YOUR_API_KEY" # Replace with your actual Pinecone API Key
        os.environ["PINECONE_ENVIRONMENT"] = "YOUR_ENVIRONMENT" # e.g., "us-west-2"

        # These are usually dummy for CI/CD or local testing
        if os.getenv("PINECONE_API_KEY") == "YOUR_API_KEY":
            logger.warning("Using dummy Pinecone API Key. Pinecone client will likely fail to connect.")
            print("Please set your PINECONE_API_KEY and PINECONE_ENVIRONMENT environment variables to run this example.")
            exit()

        pinecone_client = PineconeDBClient()

        index_name = "medical-knowledge"
        vector_dimension = 1536 # Example dimension for OpenAI embeddings
        
        # Get or create index
        medical_index = pinecone_client.get_or_create_index(index_name, dimension=vector_dimension)

        # Mock embeddings and documents
        mock_embedding_1 = [0.1] * vector_dimension
        mock_embedding_2 = [0.2] * vector_dimension
        mock_embedding_3 = [0.9] * vector_dimension # Farther embedding

        documents_to_upsert = [
            ("doc1", mock_embedding_1, {"text": "Amoxicillin is an antibiotic.", "source": "FDA"}),
            ("doc2", mock_embedding_2, {"text": "The dosage for amoxicillin is 250mg-500mg.", "source": "WHO"}),
            ("doc3", mock_embedding_3, {"text": "Symptoms of flu include fever and cough.", "source": "CDC"}),
        ]

        # Upsert documents
        pinecone_client.upsert_documents(index_name, documents_to_upsert)

        # Perform a search
        async def run_search_test():
            query_embedding = [0.15] * vector_dimension # Similar to doc1 and doc2
            print(f"\n--- Searching for a query related to amoxicillin dosage ---")
            search_results = await pinecone_client.search(query_embedding, index_name, top_k=2)
            for i, result in enumerate(search_results):
                print(f"Result {i+1} (Score: {result.get('score', 'N/A'):.4f}):")
                print(f"  ID: {result['id']}, Text: '{result['text']}'")
                print(f"  Metadata: {result['metadata']}")
            
            # Test filtering
            print("\n--- Searching with filter (source: FDA) ---")
            filtered_results = await pinecone_client.search(query_embedding, index_name, filter_clause={"source": "FDA"}, top_k=1)
            for i, result in enumerate(filtered_results):
                print(f"Filtered Result {i+1}: {result['text']}")
        
            # Test listing indexes
            print("\n--- Listing indexes ---")
            print(f"Indexes: {pinecone_client.list_indexes()}")

            # Clean up (optional: delete the index)
            # pinecone_client.pinecone.delete_index(index_name)
            # logger.info(f"Deleted index '{index_name}'.")

        import asyncio
        asyncio.run(run_search_test())
