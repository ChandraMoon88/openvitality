import logging
import os
from typing import List, Dict, Any, Optional

try:
    import chromadb
    from chromadb.utils import embedding_functions
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    embedding_functions = None
    CHROMADB_AVAILABLE = False
    logging.warning("ChromaDB library not installed. Vector database functionality will be unavailable.")

# Assuming a global config for vector DB path
from src.knowledge import get_vector_db_path

logger = logging.getLogger(__name__)

class ChromaDBClient:
    """
    A client for interacting with a local ChromaDB instance.
    Manages collections, adds documents, and performs similarity searches.
    """
    def __init__(self, persist_directory: Optional[str] = None):
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB library not found. Please install it with `pip install chromadb`.")
        
        self.persist_directory = persist_directory if persist_directory else get_vector_db_path()
        os.makedirs(self.persist_directory, exist_ok=True) # Ensure directory exists
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Default embedding function (if not provided externally)
        # ChromaDB can use its own default, or we can specify one.
        # For this context, we assume embeddings are provided or an embedding_function is set up.
        self.default_ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        
        self.collections: Dict[str, chromadb.Collection] = {}
        logger.info(f"ChromaDBClient initialized. Data will persist in: {self.persist_directory}")

    def get_or_create_collection(self, collection_name: str, embedding_function: Optional[Any] = None) -> chromadb.Collection:
        """
        Retrieves an existing collection or creates a new one.
        
        Args:
            collection_name (str): The name of the collection.
            embedding_function (Optional[Any]): The embedding function to use for this collection.
                                                  If None, uses the client's default.
        Returns:
            chromadb.Collection: The ChromaDB collection object.
        """
        if collection_name not in self.collections:
            logger.info(f"Getting or creating ChromaDB collection: '{collection_name}'")
            # For local Chroma, we don't explicitly configure HNSW or cosine at collection creation,
            # it's usually part of the internal defaults or configured at a lower level if exposed.
            # We assume it uses cosine distance for similarity by default for search operations.
            self.collections[collection_name] = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_function if embedding_function else self.default_ef
            )
            logger.debug(f"Collection '{collection_name}' ready.")
        return self.collections[collection_name]

    def add_documents(
                      self, 
                      collection_name: str,
                      documents: List[str],
                      metadatas: Optional[List[Dict[str, Any]]] = None,
                      ids: Optional[List[str]] = None,
                      embeddings: Optional[List[List[float]]] = None,
                      embedding_function: Optional[Any] = None):
        """
        Adds documents (text chunks) to a specified collection.

        Args:
            collection_name (str): The name of the collection to add to.
            documents (List[str]): A list of text documents/chunks.
            metadatas (Optional[List[Dict[str, Any]]]): List of metadata dictionaries,
                                                        one for each document.
                                                        Metadata should contain: {source, page, date, author}.
            ids (Optional[List[str]]): Optional unique IDs for each document. If None, ChromaDB generates them.
            embeddings (Optional[List[List[float]]]): Pre-computed embeddings for the documents.
                                                      If None, the collection's embedding_function will be used.
        """
        collection = self.get_or_create_collection(collection_name, embedding_function)
        
        if ids is None:
            # Generate simple IDs if not provided
            ids = [f"doc_{collection_name}_{i}" for i in range(len(documents))]
        
        # Ensure metadatas exist for all documents, even if empty
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        # ChromaDB's add method handles generating embeddings if not provided
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        logger.info(f"Added {len(documents)} documents to collection '{collection_name}'.")

    async def search(
                     self,
                     query_embedding: List[float],
                     collection_name: str,
                     top_k: int = 5,
                     where_clause: Optional[Dict[str, Any]] = None,
                     where_document_clause: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Performs a similarity search within a specified collection.

        Args:
            query_embedding (List[float]): The embedding of the query.
            collection_name (str): The name of the collection to search in.
            top_k (int): The number of top results to retrieve.
            where_clause (Optional[Dict[str, Any]]): A dictionary to filter results by metadata.
            where_document_clause (Optional[Dict[str, Any]]): A dictionary to filter results by document content.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a retrieved chunk.
                                  Each dict contains 'text', 'metadata', 'distance'.
        """
        collection = self.get_or_create_collection(collection_name)
        
        # ChromaDB query method returns results with distances
        results = collection.query(
            query_embeddings=[query_embedding], # query_embeddings is a list
            n_results=top_k,
            where=where_clause,
            where_document=where_document_clause
        )
        
        formatted_results = []
        if results and results["documents"]:
            for i in range(len(results["documents"] [0])):
                formatted_results.append({
                    "text": results["documents"] [0] [i],
                    "metadata": results["metadatas"] [0] [i] if results["metadatas"] else {},
                    "distance": results["distances"] [0] [i] if results["distances"] else None
                })
        
        logger.info(f"Searched collection '{collection_name}', retrieved {len(formatted_results)} results.")
        return formatted_results

    def get_document_by_id(self, collection_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a document by its ID from a collection.
        """
        collection = self.get_or_create_collection(collection_name)
        result = collection.get(ids=[doc_id])
        if result and result["documents"]:
            return {
                "text": result["documents"] [0],
                "metadata": result["metadatas"] [0] if result["metadatas"] else {},
                "id": result["ids"] [0]
            }
        return None

    def delete_documents(self, collection_name: str, ids: Optional[List[str]] = None, where_clause: Optional[Dict[str, Any]] = None):
        """
        Deletes documents from a collection by ID or metadata filter.
        """
        collection = self.get_or_create_collection(collection_name)
        collection.delete(ids=ids, where=where_clause)
        logger.info(f"Deleted documents from collection '{collection_name}'. IDs: {ids}, Where: {where_clause}")

    def list_collections(self) -> List[str]:
        """Lists all collections in the ChromaDB instance."""
        return [c.name for c in self.client.list_collections()]

# Example Usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    if not CHROMADB_AVAILABLE:
        print("ChromaDB not installed. Skipping example.")
    else:
        # Clean up previous run's data for a fresh start
        if os.path.exists("data/vector_store/chroma_test"):
            import shutil
            shutil.rmtree("data/vector_store/chroma_test")
            logger.info("Cleaned up previous ChromaDB test data.")

        # Initialize client with a test persistence directory
        chroma_client = ChromaDBClient(persist_directory="data/vector_store/chroma_test")

        # Get or create a collection
        medical_protocols_collection = chroma_client.get_or_create_collection("medical_protocols")

        # Define documents and metadata
        documents_to_add = [
            "Amoxicillin is an antibiotic used to treat bacterial infections. It is not effective for viral infections like the common cold.",
            "The typical adult dosage of amoxicillin is 250mg to 500mg every 8 hours, or 500mg to 875mg every 12 hours.",
            "Ibuprofen is a nonsteroidal anti-inflammatory drug (NSAID) used to reduce fever and pain.",
            "Symptoms of the common cold include runny nose, sore throat, and sneezing. Rest and fluids are recommended.",
            "Always complete the full course of antibiotics as prescribed by your doctor, even if you feel better."
        ]
        metadatas_to_add = [
            {"source": "FDA", "document": "Drug Info", "page": "1"},
            {"source": "WHO", "document": "Medical Guidelines", "page": "55"},
            {"source": "NIH", "document": "MedlinePlus", "page": "10"},
            {"source": "CDC", "document": "Common Illnesses", "page": "3"},
            {"source": "FDA", "document": "Drug Info", "page": "2"}
        ]
        ids_to_add = ["doc1", "doc2", "doc3", "doc4", "doc5"]

        # Add documents
        chroma_client.add_documents(
            collection_name="medical_protocols",
            documents=documents_to_add,
            metadatas=metadatas_to_add,
            ids=ids_to_add
        )
        
        # Test search with a query embedding (mock one for now)
        async def run_search_test():
            # In a real scenario, this would come from an embedding model
            query_text = "What is the recommended dose of amoxicillin?"
            mock_query_embedding = [0.1] * 384 # Example: a dummy embedding vector

            print(f"\n--- Searching for: '{query_text}' ---")
            search_results = await chroma_client.search(mock_query_embedding, "medical_protocols", top_k=2)
            for i, result in enumerate(search_results):
                print(f"Result {i+1} (Distance: {result.get('distance', 'N/A'):.4f}):")
                print(f"  Text: '{result['text']}'")
                print(f"  Metadata: {result['metadata']}")
            
            # Test filtering
            print("\n--- Searching with filter (source: WHO) ---")
            filtered_results = await chroma_client.search(mock_query_embedding, "medical_protocols", where_clause={"source": "WHO"}, top_k=1)
            for i, result in enumerate(filtered_results):
                print(f"Filtered Result {i+1}: '{result['text']}'")
            
            # Test getting document by ID
            print("\n--- Getting document by ID 'doc4' ---")
            doc4 = chroma_client.get_document_by_id("medical_protocols", "doc4")
            if doc4:
                print(f"Document 4: '{doc4['text']}'")
        
            # Test listing collections
            print("\n--- Listing collections ---")
            print(f"Collections: {chroma_client.list_collections()}")

        import asyncio
        asyncio.run(run_search_test())
        
        # Cleanup
        # If running in persistent mode, explicit deletion might be needed,
        # otherwise just removing the directory is enough for a test run.
        # This is already handled by the initial shutil.rmtree.
