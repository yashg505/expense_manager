import os
import faiss
import numpy as np
from src.logger import get_logger

logger = get_logger(__name__)

class FaissStore:
    def __init__(self, index_path: str):
        """
        Initialize the FaissStore with a path to the index file.
        """
        self.index_path = index_path
        self.index = None
        logger.debug(f"FaissStore initialized with index_path: {self.index_path}")

    def build_new_index(self, vectors: np.ndarray):
        """
        Create a new FAISS index from a set of vectors and save it to disk.
        
        Args:
            vectors: A numpy array of shape (N, D) where N is the number of vectors
                    and D is the dimensionality of the embeddings.
        """
        try:
            # Ensure vectors are float32 (required by FAISS)
            vectors = np.array(vectors).astype('float32')
            dimension = vectors.shape[1]
            
            logger.info(f"Building new FAISS index with {len(vectors)} vectors of dimension {dimension}")
            
            # Using IndexFlatL2 for exact search based on Euclidean distance
            self.index = faiss.IndexFlatL2(dimension)
            self.index.add(vectors)
            
            # Save the index to disk
            os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            
            logger.info(f"FAISS index successfully built and saved to {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}")
            raise

    def load(self):
        """
        Load the FAISS index from disk into memory.
        """
        try:
            if not os.path.exists(self.index_path):
                msg = f"FAISS index file not found at: {self.index_path}"
                logger.error(msg)
                raise FileNotFoundError(msg)
            
            self.index = faiss.read_index(self.index_path)
            logger.info(f"FAISS index loaded successfully from {self.index_path}")
        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            raise

    def search(self, query_vector: np.ndarray, k: int = 5):
        """
        Search the index for the k nearest neighbors to the given query vector.
        
        Args:
            query_vector: A numpy array of shape (D,) or (1, D).
            k: The number of nearest neighbors to return.
            
        Returns:
            indices: Array of indices of the k nearest neighbors.
            distances: Array of distances to the k nearest neighbors.
        """
        try:
            if self.index is None:
                logger.debug("Index not loaded, attempting to load...")
                self.load()
            
            # Ensure query_vector is float32 and correctly shaped (1, D)
            query_vector = np.array(query_vector).astype('float32')
            if len(query_vector.shape) == 1:
                query_vector = query_vector.reshape(1, -1)
            
            logger.debug(f"Searching FAISS index for k={k} nearest neighbors")
            distances, indices = self.index.search(query_vector, k)
            
            # Flatten to return 1D arrays since we only searched for one vector
            return indices[0], distances[0]
        except Exception as e:
            logger.error(f"Failed to search FAISS index: {e}")
            raise
