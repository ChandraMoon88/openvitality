# src/knowledge/__init__.py

import logging
from typing import Dict, Type, Any, Optional

logger = logging.getLogger(__name__)

# --- Vector DB Configuration ---
_VECTOR_DB_PATH: str = "data/vector_store/chroma" # Default path for local ChromaDB

def set_vector_db_path(path: str):
    """Sets the global path for the vector database."""
    global _VECTOR_DB_PATH
    _VECTOR_DB_PATH = path
    logger.info(f"Vector DB path set to: '{_VECTOR_DB_PATH}'.")

def get_vector_db_path() -> str:
    """Returns the global path for the vector database."""
    return _VECTOR_DB_PATH

# --- Embedding Model Registry ---
_EMBEDDING_MODEL_REGISTRY: Dict[str, Type[Any]] = {}
_LOADED_EMBEDDING_MODELS: Dict[str, Any] = {}

def register_embedding_model(name: str, model_class: Type[Any]):
    """Registers an embedding model class with the registry."""
    if name in _EMBEDDING_MODEL_REGISTRY:
        logger.warning(f"Embedding model '{name}' already registered. Overwriting.")
    _EMBEDDING_MODEL_REGISTRY[name] = model_class
    logger.debug(f"Embedding model '{name}' registered.")

def get_embedding_model(name: str, **kwargs) -> Any:
    """
    Retrieves and lazily loads an embedding model instance.
    If the model is already loaded, returns the existing instance.
    """
    if name not in _EMBEDDING_MODEL_REGISTRY:
        raise ValueError(f"Embedding model '{name}' not registered.")
    
    if name not in _LOADED_EMBEDDING_MODELS:
        logger.info(f"Lazily loading embedding model: '{name}'.")
        _LOADED_EMBEDDING_MODELS[name] = _EMBEDDING_MODEL_REGISTRY[name](**kwargs)
    
    return _LOADED_EMBEDDING_MODELS[name]

# --- Document Loader Registry ---
_DOCUMENT_LOADER_REGISTRY: Dict[str, Type[Any]] = {}

def register_document_loader(file_extension: str, loader_class: Type[Any]):
    """Registers a document loader class with the registry for a specific file extension."""
    if file_extension in _DOCUMENT_LOADER_REGISTRY:
        logger.warning(f"Document loader for extension '{file_extension}' already registered. Overwriting.")
    _DOCUMENT_LOADER_REGISTRY[file_extension] = loader_class
    logger.debug(f"Document loader for '{file_extension}' registered.")

def get_document_loader(file_extension: str, **kwargs) -> Any:
    """
    Retrieves and instantiates a document loader for a given file extension.
    """
    loader_class = _DOCUMENT_LOADER_REGISTRY.get(file_extension)
    if not loader_class:
        raise ValueError(f"Document loader for extension '{file_extension}' not registered.")
    
    logger.info(f"Creating document loader for '{file_extension}'.")
    return loader_class(**kwargs)

logger.info("src.knowledge package initialized.")