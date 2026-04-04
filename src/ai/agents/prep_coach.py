import json
from sqlalchemy.orm import Session

from src.services.llm_service import ask_llm
from src.services.embedding_service import get_embedding
from src.ai.prompts.prep_coach_prompts import PREP_COACH_SYSTEM_PROMPT
from src.models.setup import CasePrep, ArgumentEmbedding


def ensure_string(text):
    """
    Ensures text is always a string (LLM safety)
    """
    if isinstance(text, str):
        return text
    return str(text)


def generate_case_prep(
    db: Session,
    case_prep_id: str,
    motion_text: str,
    side: str
) -> bool:
    """
    Main Prep Coach pipeline:
    LLM → JSON → DB → Embeddings → DB
    """

    try:
        # 1️⃣ Fetch CasePrep
        case_prep = db.query(CasePrep).filter(CasePrep.id == case_prep_id).first()

        if not case_prep:
            print("❌ CasePrep not found")
            return False

        # 2️⃣ Create user prompt
        user_prompt = f"""
        Motion: {motion_text}
        Side: {side}
        Skill Level: Beginner
        """

        # 3️⃣ Call LLM
        print("🧠 Generating AI Case Prep...")

        response = ask_llm(
            system_prompt=PREP_COACH_SYSTEM_PROMPT,
            user_prompt=user_prompt
        )

        # 4️⃣ Parse JSON
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            print("❌ LLM did not return valid JSON")
            print(response)
            return False

        # 5️⃣ Save structured data
        case_prep.model_definition = data.get("model_definition")
        case_prep.arguments = data.get("arguments")
        case_prep.counter_arguments = data.get("counter_arguments")
        case_prep.evidence = data.get("evidence")

        db.add(case_prep)
        db.commit()

        print("✅ CasePrep JSON saved")

        # 6️⃣ Prepare text for embeddings (SAFE)
        all_texts = []

        for arg in data.get("arguments", []):
            all_texts.append((ensure_string(arg), "argument"))

        for arg in data.get("counter_arguments", []):
            all_texts.append((ensure_string(arg), "counter_argument"))

        for arg in data.get("evidence", []):
            all_texts.append((ensure_string(arg), "evidence"))

        print("🧠 Generating embeddings...")

        # 7️⃣ Generate and store embeddings
        for text, arg_type in all_texts:
            try:
                embedding = get_embedding(text)

                emb = ArgumentEmbedding(
                    case_prep_id=case_prep.id,
                    content=text,
                    embedding=embedding,
                    argument_type=arg_type
                )

                db.add(emb)

            except Exception as embed_error:
                print(f"⚠️ Skipping embedding for text: {text}")
                print(f"Reason: {embed_error}")
                continue  # don't crash entire pipeline

        db.commit()

        print("✅ Embeddings stored successfully")

        return True

    except Exception as e:
        print(f"❌ Error in Prep Coach: {e}")
        db.rollback()
        return False