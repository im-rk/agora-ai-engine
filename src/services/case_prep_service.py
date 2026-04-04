"""
Case Prep Service: Orchestrates case preparation workflow.

This service bridges the gap between the FastAPI layer and the AI agent.
It:
1. Calls the Prep Coach AI agent
2. Validates the response
3. Saves the result to the database via repository
4. Logs the AI call to AICallLog (Langfuse) for observability
"""

import json
from sqlalchemy.orm import Session
from typing import Dict, Any

from src.ai.agents.prep_coach import generate_case_prep
from src.repositories.case_prep_repo import update_case_prep, save_ai_call_log


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
    Orchestrates case preparation workflow: agent call, validation, DB save, logging.
    
    Args:
        db: SQLAlchemy session
        user_id: User UUID
        motion_id: Motion UUID
        session_id: Debate session UUID (for AICallLog linking)
        case_prep_id: Case prep UUID
        motion_text: Debate motion
        side: Government or Opposition
        format: BP or AP
    
    Returns:
        Dict with case preparation data
    
    Raises:
        ValueError: If AI response validation fails
    """
    prompt_payload = {
        "motion_text": motion_text,
        "side": side,
        "format": format
    }

    try:
        ai_response = await generate_case_prep(
            motion_text=motion_text,
            side=side,
            format=format
        )

        if not isinstance(ai_response, dict):
            raise ValueError("AI agent did not return a dictionary")

        required_keys = {"model_definition", "arguments", "counter_arguments", "evidence"}
        if not required_keys.issubset(ai_response.keys()):
            missing = required_keys - set(ai_response.keys())
            raise ValueError(f"AI response missing required keys: {missing}")
        update_case_prep(
            db=db,
            case_prep_id=case_prep_id,
            model_definition=ai_response.get("model_definition"),
            arguments=ai_response.get("arguments"),
            counter_arguments=ai_response.get("counter_arguments"),
            evidence=ai_response.get("evidence")
        )

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
