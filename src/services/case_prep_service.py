"""
Case Prep Service: Orchestrates case preparation workflow.

Responsibilities:
  1. Call Prep Coach AI agent to generate case preparation
  2. Validate structured response
  3. Persist case prep data to database
  4. Generate embeddings for semantic search
  5. Log AI call for observability (Langfuse)
"""

import json
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.ai.agents.prep_coach import generate_case_prep
from src.repositories.case_prep_repo import update_case_prep, save_ai_call_log
from src.services.embedding_service import get_embedding
from src.models.setup import ArgumentEmbedding


async def prepare_case(
    db: Session,
    user_id: str,
    motion_id: str,
    session_id: str,
    case_prep_id: str,
    motion_text: str,
    side: str,
    format: str
) -> Dict[str, Any]:
    """
    Orchestrates case preparation workflow.
    
    Args:
        db: Database session
        user_id: User ID
        motion_id: Motion ID
        session_id: Debate session ID
        case_prep_id: Case prep record ID
        motion_text: The debate motion
        side: Government or Opposition
        format: Debate format (BP/AP)
    
    Returns:
        AI-generated case preparation data
    
    Raises:
        ValueError: If AI generation or validation fails
    """

    prompt_payload = {
        "motion_text": motion_text,
        "side": side,
        "format": format
    }

    try:
        # Step 1: Call AI agent
        ai_response = await generate_case_prep(
            motion_text=motion_text,
            side=side,
            format=format
        )

        # Step 2: Validate response structure
        if hasattr(ai_response, "model_dump"):
            ai_response = ai_response.model_dump()
        elif hasattr(ai_response, "dict"):
            ai_response = ai_response.dict()
        elif isinstance(ai_response, str):
            try:
                cleaned = ai_response.strip("`")
                if cleaned.startswith("json\n"):
                    cleaned = cleaned[5:]
                ai_response = json.loads(cleaned)
            except Exception:
                raise ValueError(f"AI response string is not valid JSON. Got: {ai_response[:100]}")
                
        if not isinstance(ai_response, dict):
            raise ValueError(f"AI agent response must be a dictionary, got {type(ai_response)}")

        required_keys = {"model_definition", "arguments", "counter_arguments", "evidence"}
        missing_keys = required_keys - set(ai_response.keys())
        if missing_keys:
            raise ValueError(f"AI response missing keys: {missing_keys}")

        # Step 3: Persist case prep to database
        update_case_prep(
            db=db,
            case_prep_id=case_prep_id,
            model_definition=ai_response.get("model_definition"),
            arguments=ai_response.get("arguments"),
            counter_arguments=ai_response.get("counter_arguments"),
            evidence=ai_response.get("evidence")
        )

        # Step 4: Generate embeddings for semantic search
        embedding_texts = []
        
        for arg in ai_response.get("arguments", []):
            if isinstance(arg, dict) and "claim" in arg:
                embedding_texts.append((arg["claim"], "argument"))

        for counter_arg in ai_response.get("counter_arguments", []):
            if counter_arg:
                embedding_texts.append((counter_arg, "counter_argument"))

        for evidence in ai_response.get("evidence", []):
            if evidence:
                embedding_texts.append((evidence, "evidence"))

        # Store embeddings
        for content, arg_type in embedding_texts:
            try:
                embedding_vector = get_embedding(content)
                embedding_record = ArgumentEmbedding(
                    case_prep_id=case_prep_id,
                    content=content,
                    embedding=embedding_vector,
                    argument_type=arg_type
                )
                db.add(embedding_record)
            except Exception as e:
                # Log but don't fail on embedding errors
                print(f"Warning: Embedding generation failed for content: {content[:50]}... ({str(e)})")

        db.commit()

        # Step 5: Log AI call for observability
        save_ai_call_log(
            db=db,
            session_id=session_id,
            agent_name="prep_coach",
            prompt_used=json.dumps(prompt_payload),
            model_version="gpt-4o-mini",
            temperature=0.7,
            raw_output=json.dumps(ai_response, indent=2)
        )

        return ai_response

    except Exception as e:
        db.rollback()
        raise