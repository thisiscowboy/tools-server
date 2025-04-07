"""
Embeddings model implementation using Hugging Face Transformers.
Provides text embedding generation and similarity calculation functionality.
"""
import os
import logging
from typing import List, Optional
import numpy as np
import torch
from transformers import AutoModel
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class HfEmbeddings:
    """
    Hugging Face embeddings model class that handles text embedding generation
    and similarity calculations using pre-trained transformer models.
    """
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize Embeddings model
        """
        model_name = model_name or os.getenv("EMBEDDING_MODEL", "")
        logger.info("Loading embeddings model: %s", model_name)

        try:
            self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
            # Move to GPU if available
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model.to(self.device)
            logger.info("Model loaded successfully on %s", self.device)
        except Exception as e:
            logger.error("Error loading model: %s", str(e))
            logger.error("Please make sure you are logged into Hugging Face. "
                         "Run: huggingface-cli login")
            raise

    def embed(self, text: str, max_length: int = 2048) -> List[float]:
        """
        Generate embeddings for a single text
        """
        return self.embed_batch([text], max_length)[0]

    def embed_batch(self, texts: List[str], max_length: int = 2048) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts
        """
        try:
            with torch.no_grad():
                embeddings = self.model.encode(texts, max_length=max_length)

            # Convert to Python list for JSON serialization
            if isinstance(embeddings, torch.Tensor):
                embeddings = embeddings.cpu().numpy()

            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()

            return embeddings
        except Exception as e:
            logger.error("Error generating embeddings: %s", str(e))
            raise

    def similarity(self, text1: str, text2: str) -> float:
        """
        Calculate cosine similarity between two texts
        """
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)

        # Compute cosine similarity
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        magnitude1 = sum(a * a for a in emb1) ** 0.5
        magnitude2 = sum(b * b for b in emb2) ** 0.5

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)