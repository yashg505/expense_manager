import numpy as np
from expense_manager.utils.load_config import load_config_file
from expense_manager.logger import get_logger

logger = get_logger(__name__)

# We prefer an ONNX-based embedding backend (fastembed) to avoid pulling in torch + CUDA
# dependencies on Linux. If fastembed isn't available, we fall back to SentenceTransformer.
_EMBEDDING_BACKEND = None  # "fastembed" | "sentence_transformers"
_EMBEDDING_MODEL = None

def _get_backend_and_model():
    global _EMBEDDING_BACKEND, _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is not None:
        return _EMBEDDING_BACKEND, _EMBEDDING_MODEL

    cfg_name = load_config_file().get("llm", {}).get("embedding_model") or ""

    # Try fastembed first
    try:
        from fastembed import TextEmbedding  # type: ignore

        # fastembed has its own model naming; default to a small 384-dim model.
        model_name = cfg_name or "BAAI/bge-small-en-v1.5"
        logger.info(f"Loading fastembed model: {model_name}")
        _EMBEDDING_BACKEND = "fastembed"
        _EMBEDDING_MODEL = TextEmbedding(model_name=model_name)
        return _EMBEDDING_BACKEND, _EMBEDDING_MODEL
    except Exception as e:
        logger.warning(f"fastembed unavailable/failed to init ({e}); falling back to sentence-transformers.")

    # Fallback to sentence-transformers (heavier)
    from sentence_transformers import SentenceTransformer  # type: ignore

    model_name = cfg_name or "all-MiniLM-L6-v2"
    logger.info(f"Loading SentenceTransformer model: {model_name}")
    _EMBEDDING_BACKEND = "sentence_transformers"
    _EMBEDDING_MODEL = SentenceTransformer(model_name)
    return _EMBEDDING_BACKEND, _EMBEDDING_MODEL

def embed_texts(texts: list[str]) -> np.ndarray:
    """
    Generates embeddings for a list of strings using a local embedding backend.
    
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

    backend, model = _get_backend_and_model()

    try:
        logger.info(f"Generating embeddings for {len(texts)} texts locally.")

        if backend == "fastembed":
            # fastembed yields an iterator of np arrays
            embeddings = list(model.embed(texts))
        else:
            embeddings = model.encode(texts, show_progress_bar=False)
        
        # Convert to numpy array with float32 type for pgvector compatibility
        vector_array = np.array(embeddings).astype('float32')
        
        logger.info(f"Successfully generated embeddings. Shape: {vector_array.shape}")
        return vector_array

    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}")
        raise
