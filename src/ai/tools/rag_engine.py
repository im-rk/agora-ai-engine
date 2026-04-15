"""
RAG Engine: Retrieval-Augmented Generation for debate case prep.

Uses Supabase pgvector for semantic search over prepared arguments,
counter-arguments, and evidence to support live debate responses.
"""

from functools import lru_cache
from supabase import create_client
from pgvector.sqlalchemy import Vector
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models.setup import ArgumentEmbedding
from src.core.config import settings
from src.services.embedding_service import get_embedding

class CohereEmbeddingWrapper:
    def embed_query(self, text: str) -> list[float]:
        return get_embedding(text)

@lru_cache(maxsize=1)
def get_embeddings_model():
    """Get Cohere embeddings model to match database seeding and avoid 1.4GB local download."""
    return CohereEmbeddingWrapper()


class RAGEngine:
    """Retrieval-Augmented Generation engine for debate responses."""
    
    def __init__(self):
        """Initialize RAG engine with embeddings model."""
        self.embeddings = get_embeddings_model()
    
    async def aretrieve_counter_arguments(
        self,
        topic: str,
        k: int = 3
    ) -> list[dict]:
        """
        Async retrieve relevant evidence for a given topic using pgvector.
        
        Performs semantic search over stored arguments using cosine similarity.
        
        Args:
            topic: Search topic or opponent claim
            k: Number of results to retrieve
        
        Returns:
            List of dicts with ['text', 'score', 'id'] keys
        """
        db = None
        try:
            # Embed the query
            query_embedding = self.embeddings.embed_query(topic)
            
            # Get database session and perform vector search
            db = SessionLocal()
            
            # Use pgvector similarity search (cosine distance)
            results = db.query(
                ArgumentEmbedding.id,
                ArgumentEmbedding.content,
                ArgumentEmbedding.argument_type,
                (ArgumentEmbedding.embedding.cosine_distance(query_embedding)).label("distance")
            ).order_by("distance").limit(k).all()
            
            # Format results (lower distance = higher similarity)
            formatted = []
            for result_id, content, arg_type, distance in results:
                # Convert distance to similarity score (0-1 range)
                similarity_score = 1 - distance  # Cosine distance to similarity
                formatted.append({
                    "text": content,
                    "score": float(similarity_score),
                    "id": str(result_id),
                    "source": "case_prep",
                    "type": arg_type
                })
            
            return formatted
        
        except Exception as e:
            if str(e).strip():
                print(f"Error retrieving evidence: {type(e).__name__}: {str(e)[:200]}")
            return []
        finally:
            if db:
                db.close()
    
    async def retrieve_counter_arguments(
        self,
        opponent_claim: str,
        k: int = 3
    ) -> str:
        """
        Legacy sync-style async retrieve (returns formatted string).
        
        For backward compatibility with existing code that expects
        a formatted string output instead of structured results.
        
        Args:
            opponent_claim: The opponent's stated claim or argument
            k: Number of results to retrieve
        
        Returns:
            Formatted string with relevant case prep material
        """
        results = await self.aretrieve_counter_arguments(opponent_claim, k=k)
        
        if not results:
            return "No specific case prep found for this point. Rely on general debate principles."
        
        return "\n\n".join([r["text"] for r in results])