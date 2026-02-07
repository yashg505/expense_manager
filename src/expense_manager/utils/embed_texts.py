import numpy as np
from expense_manager.logger import get_logger

logger = get_logger(__name__)

# Global cache to avoid re-loading the model on every request.
_EMBEDDING_MODEL = None

def _get_model():
    """Lazy load the SentenceTransformer embedding model."""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from expense_manager.utils.load_config import load_config_file
        from sentence_transformers import SentenceTransformer  # type: ignore

        model_name = load_config_file().get("llm", {}).get("embedding_model", "all-MiniLM-L6-v2")
        logger.info(f"Loading SentenceTransformer model: {model_name}")
        _EMBEDDING_MODEL = SentenceTransformer(model_name)
    return _EMBEDDING_MODEL

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Generates embeddings for a list of strings using SentenceTransformer.
    
    Args:
        texts: A list of strings to be embedded.
        
    Returns:
        A numpy array of shape (N, D) where N is the number of input strings 
        and D is the dimensionality of the embeddings.
    """
    if not texts:
        logger.warning("Empty list of texts passed to embed_texts.")
        return np.array([]).astype('float32')

    # Ensure single string is treated as a list
    if isinstance(texts, str):
        texts = [texts]

    model = _get_model()

    try:
        logger.info(f"Generating embeddings for {len(texts)} texts locally.")
        embeddings = model.encode(texts, show_progress_bar=False)
        
        # Convert to numpy array with float32 type for pgvector compatibility
        vector_array = np.array(embeddings).astype('float32')
        
        logger.info(f"Successfully generated embeddings. Shape: {vector_array.shape}")
        return vector_array

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise
