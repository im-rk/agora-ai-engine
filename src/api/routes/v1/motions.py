import logging
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.ai.clients.groq_client import get_groq_client
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.common import APIResponse, APIStatusCode
from src.api.dependencies import get_current_user
from src.schemas.auth import CurrentUserData

logger = logging.getLogger(__name__)
router = APIRouter()

class GenerateMotionRequest(BaseModel):
    category: str = "Global"
    format: str = "bp"  # "ap" or "bp"

class GenerateMotionResponse(BaseModel):
    motion: str
    info: str

@router.post(
    "/generate",
    response_model=APIResponse[GenerateMotionResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate a debate motion"
)
async def generate_motion(
    request: GenerateMotionRequest,
    user: CurrentUserData = Depends(get_current_user)
):
    try:
        llm = get_groq_client(streaming=False, temperature=0.9)
        
        system_prompt = (
            f"You are an expert parliamentary debate adjudicator. "
            f"Your task is to generate a highly competitive, nuanced, and realistic debate motion for the {request.format.upper()} format.\n"
            f"The motion should fall under the category: '{request.category}'.\n"
            "Respond ONLY with a JSON object containing two keys:\n"
            '1. "motion": The motion text (e.g., "This House Would...").\n'
            '2. "info": A brief background context or definition of key terms in the motion (1-2 sentences).\n'
            "Ensure the JSON is valid and can be parsed."
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content="Generate a new debate motion now.")
        ]
        
        response = await llm.ainvoke(messages)
        
        try:
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            data = json.loads(content)
            
            return APIResponse(
                status=APIStatusCode.SUCCESS,
                message="Motion generated",
                data=GenerateMotionResponse(
                    motion=data.get("motion", "This house believes..."),
                    info=data.get("info", "No additional context provided.")
                )
            )
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from LLM: {response.content}")
            return APIResponse(
                status=APIStatusCode.SUCCESS,
                message="Fallback motion",
                data=GenerateMotionResponse(
                    motion="This House Believes That AI will do more harm than good.",
                    info="A classic debate on the long-term impacts of Artificial Intelligence on humanity."
                )
            )

    except Exception as e:
        logger.error(f"Failed to generate motion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate motion"
        )
