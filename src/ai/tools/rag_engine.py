"""
RAG Engine: Retrieval-Augmented Generation for debate case prep.

Uses Supabase pgvector for semantic search over prepared arguments,
counter-arguments, and evidence to support live debate responses.
"""

from functools import lru_cache
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client
from src.core.config import settings


@lru_cache(maxsize=1)
def get_vector_store() -> SupabaseVectorStore:
    """
    Get Supabase vector store instance (cached singleton).
    
    Uses HuggingFace embeddings for free, local embedding generation.
    Connects to Supabase pgvector for semantic search.
    
    Returns:
        SupabaseVectorStore instance
    
    Raises:
        ValueError: If Supabase credentials not configured
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be configured")
    
    supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"}
    )
    
    return SupabaseVectorStore(
        client=supabase_client,
        embedding=embeddings,
        table_name="argument_embeddings",
        query_name="match_documents"
    )


class RAGEngine:
    """Retrieval-Augmented Generation engine for debate responses."""
    
    def __init__(self):
        """Initialize RAG engine with cached vector store."""
        self.vector_store = get_vector_store()
    
    async def aretrieve_counter_arguments(
        self,
        topic: str,
        k: int = 3
    ) -> list[dict]:
        """
        Async retrieve relevant evidence for a given topic.
        
        Performs semantic search over stored arguments, counter-arguments,
        and evidence. Returns results as dicts for further re-ranking.
        
        Args:
            topic: Search topic or opponent claim
            k: Number of results to retrieve
        
        Returns:
            List of dicts with ['text', 'score', 'id'] keys
        """
        try:
            # Perform similarity search
            docs = self.vector_store.similarity_search_with_score(topic, k=k)
            
            # Format results
            results = []
            for doc, score in docs:
                results.append({
                    "text": doc.page_content,
                    "score": score,
                    "id": doc.metadata.get("id", hash(doc.page_content)),
                    "source": doc.metadata.get("source", "case_prep")
                })
            
            return results
        
        except Exception as e:
            print(f"Error retrieving evidence: {e}")
            return []
    
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