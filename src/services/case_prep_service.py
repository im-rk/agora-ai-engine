"""
Case Prep Service: Orchestrates case preparation workflow.

This service bridges the gap between the FastAPI layer and the AI agent.
It:
1. Calls the Prep Coach AI agent
2. Validates the response
3. Saves the result to the database via repository
4. Generates embeddings for semantic search
5. Logs the AI call to AICallLog (Langfuse) for observability
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
    Orchestrates case preparation workflow: agent call, validation, DB save, embeddings, logging.
    """

    prompt_payload = {
        "motion_text": motion_text,
        "side": side,
        "format": format
    }

    try:
        # ----------------------------
        # 1️ CALL AI AGENT
        # ----------------------------
        ai_response = await generate_case_prep(
            motion_text=motion_text,
            side=side,
            format=format
        )

        # ----------------------------
        # 2️ VALIDATE RESPONSE
        # ----------------------------
        if not isinstance(ai_response, dict):
            raise ValueError("AI agent did not return a dictionary")

        required_keys = {"model_definition", "arguments", "counter_arguments", "evidence"}
        if not required_keys.issubset(ai_response.keys()):
            missing = required_keys - set(ai_response.keys())
            raise ValueError(f"AI response missing required keys: {missing}")

        # ----------------------------
        # 3️ SAVE CASE PREP (JSON)
        # ----------------------------
        update_case_prep(
            db=db,
            case_prep_id=case_prep_id,
            model_definition=ai_response.get("model_definition"),
            arguments=ai_response.get("arguments"),
            counter_arguments=ai_response.get("counter_arguments"),
            evidence=ai_response.get("evidence")
        )

        # ----------------------------
        # 4️ GENERATE EMBEDDINGS 
        # ----------------------------
        all_texts = []

        # Arguments (structured)
        for arg in ai_response.get("arguments", []):
            if isinstance(arg, dict):
                claim = arg.get("claim", "")
                if claim:
                    all_texts.append((claim, "argument"))

        # Counter arguments
        for arg in ai_response.get("counter_arguments", []):
            if arg:
                all_texts.append((arg, "counter_argument"))

        # Evidence
        for ev in ai_response.get("evidence", []):
            if ev:
                all_texts.append((ev, "evidence"))

        # Generate + store embeddings
        for text, arg_type in all_texts:
            try:
                embedding = get_embedding(text)

                emb = ArgumentEmbedding(
                    case_prep_id=case_prep_id,
                    content=text,
                    embedding=embedding,
                    argument_type=arg_type
                )

                db.add(emb)

            except Exception as emb_error:
                print(f"⚠️ Embedding failed for text: {text[:50]}... Error: {emb_error}")

        db.commit()

        print("✅ Embeddings stored successfully")

        # ----------------------------
        # 5️ LOG AI CALL
        # ----------------------------
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
        print(f" Error in prepare_case: {e}")
        raise