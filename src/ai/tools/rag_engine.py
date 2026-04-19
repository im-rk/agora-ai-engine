"""
RAG Engine: Retrieval-Augmented Generation for debate case prep.

Uses PostgreSQL pgvector for semantic search over prepared arguments,
counter-arguments, and evidence to support live debate responses.

Features:
- Same-match filtering: Get arguments from THIS debate only
- Side filtering: Get Government or Opposition arguments
- Role filtering: Get arguments for specific roles
- Metadata-aware: Smart filtering prevents confusion
"""

from functools import lru_cache
from typing import Optional, List, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from pgvector.sqlalchemy import Vector
from sqlalchemy import func
from sqlalchemy.orm import Session
from src.core.database import SessionLocal
from src.models.setup import ArgumentEmbedding
from src.core.config import settings
import logging

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embeddings_model():
    """Get cached HuggingFace embeddings model."""
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-roberta-large-v1",
        model_kwargs={"device": "cpu"}
    )


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for debate responses.
    
    ONLY used in Debater Agent to retrieve relevant arguments/counter-arguments
    from vector database during live debate.
    
    Uses metadata filtering to ensure arguments are:
    - From the SAME debate (match_id filter)
    - From the CORRECT side (side filter)
    - Relevant to the debater's ROLE (role filter)
    """
    
    def __init__(self):
        """Initialize RAG engine with embeddings model."""
        self.embeddings = get_embeddings_model()
    
    async def aretrieve_counter_arguments(
        self,
        topic: str,
        match_id: str,
        side: str,
        role: Optional[str] = None,
        k: int = 3
    ) -> List[Dict]:
        """
        Async retrieve relevant counter-arguments for a given topic WITH metadata filtering.
        
        USED IN: Debater Agent during live debate
        
        Performs semantic search over stored arguments using cosine similarity,
        but ONLY returns arguments from:
        - THIS SPECIFIC debate (match_id filter)
        - SAME SIDE as debater (side filter)
        - Optional: SAME ROLE as debater (role filter)
        
        Args:
            topic: Search topic or point to counter (e.g., "healthcare prevents poverty")
            match_id: UUID of current debate (FILTER BY THIS)
            side: "Government" or "Opposition" (FILTER BY THIS)
            role: Optional - debater role (e.g., "opening_government")
            k: Number of results to retrieve (default: 3)
        
        Returns:
            List of dicts with ['text', 'score', 'id', 'type'] keys
        
        """
        db = None
        try:
            # Embed the query
            query_embedding = self.embeddings.embed_query(topic)
            
            # Get database session
            db = SessionLocal()
            
            # Build filter query: ONLY from this debate, this side
            query_obj = db.query(
                ArgumentEmbedding.id,
                ArgumentEmbedding.content,
                ArgumentEmbedding.argument_type,
                ArgumentEmbedding.embedding
            ).filter(
                ArgumentEmbedding.match_id == match_id,  
                ArgumentEmbedding.side == side           
            )
            
            # Optional: Filter by role if provided
            if role:
                query_obj = query_obj.filter(ArgumentEmbedding.role == role)
            
            # Perform pgvector similarity search (cosine distance)
            results = query_obj.order_by(
                ArgumentEmbedding.embedding.op("<->")(query_embedding)
            ).limit(k).all()
            
            if not results:
                logger.info(f"No arguments found for match={match_id}, side={side}, role={role}")
                return []
            
            # Format results (lower distance = higher similarity)
            formatted = []
            for result_id, content, arg_type, embedding in results:
                # Calculate similarity (1 - cosine_distance for 0-1 range)
                # Compute distance
                distance = float((embedding - query_embedding).dot(embedding - query_embedding) ** 0.5)
                similarity_score = 1 - min(distance, 1.0)  # Normalize to 0-1
                
                formatted.append({
                    "text": content,
                    "score": similarity_score,
                    "id": str(result_id),
                    "source": "case_prep",
                    "type": arg_type
                })
            
            logger.info(f"Retrieved {len(formatted)} arguments for match={match_id}, side={side}")
            return formatted
        
        except Exception as e:
            if str(e).strip():
                logger.error(f"Error retrieving counter-arguments: {type(e).__name__}: {str(e)[:200]}")
            return []
        finally:
            if db:
                db.close()
    
    async def retrieve_counter_arguments(
        self,
        opponent_claim: str,
        match_id: str,
        side: str,
        role: Optional[str] = None,
        k: int = 3
    ) -> str:
        """
        Retrieve counter-arguments and return as formatted string.
        
        USED IN: Debater Agent (wrapper around aretrieve_counter_arguments)
        
        Filters by metadata to ensure relevant results from THIS debate only.
        
        Args:
            opponent_claim: The opponent's stated claim or argument
            match_id: UUID of current debate (FILTER BY THIS)
            side: "Government" or "Opposition" (FILTER BY THIS)
            role: Optional - debater role
            k: Number of results to retrieve
        
        Returns:
            Formatted string with relevant case prep material, or fallback message
        
        """
        results = await self.aretrieve_counter_arguments(
            topic=opponent_claim,
            match_id=match_id,
            side=side,
            role=role,
            k=k
        )
        
        if not results:
            logger.warning(f"No case prep found for: {opponent_claim[:50]}... in match {match_id}")
            return "No specific case prep found for this point. Rely on general debate principles."
        
        # Format as string for debater agent
        formatted_output = "\n\n".join([
            f"[{r['type'].upper()}] {r['text']} (relevance: {r['score']:.2f})"
            for r in results
        ])
        
        logger.info(f"Formatted {len(results)} results for debater")
        return formatted_output