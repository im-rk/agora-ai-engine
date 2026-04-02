from sqlalchemy.orm import Session
from sqlalchemy import select

from src.models.setup import CasePrep, ArgumentEmbedding
from src.services.embedding_service import get_embedding


# -----------------------------------
# CREATE CASE PREP (IDEMPOTENT)
# -----------------------------------
def create_case_prep(
    db: Session,
    user_id,
    motion_id,
    side,
    prep_data: dict
):
    # 🔥 Check if already exists
    existing = db.execute(
        select(CasePrep).where(
            CasePrep.user_id == user_id,
            CasePrep.motion_id == motion_id,
            CasePrep.side == side
        )
    ).scalars().first()

    if existing:
        print("⚠️ CasePrep already exists, reusing...")
        return existing, True   # True = already existed

    # ✅ Create new
    case_prep = CasePrep(
        user_id=user_id,
        motion_id=motion_id,
        side=side,
        model_definition=prep_data.get("model_definition"),
        arguments=prep_data.get("arguments"),
        counter_arguments=prep_data.get("counter_arguments"),
        evidence=prep_data.get("evidence"),
    )

    db.add(case_prep)
    db.commit()
    db.refresh(case_prep)

    return case_prep , False  # False = newly created


# -----------------------------------
# STORE EMBEDDINGS (NO DUPLICATES)
# -----------------------------------
def store_argument_embeddings(db: Session, case_prep, prep_data: dict):

    # 🔥 Check if embeddings already exist
    existing = db.execute(
        select(ArgumentEmbedding).where(
            ArgumentEmbedding.case_prep_id == case_prep.id
        )
    ).scalars().first()

    if existing:
        print("⚠️ Embeddings already exist, skipping...")
        return

    arguments = prep_data.get("arguments", [])

    for arg in arguments:
        # ✅ Handle structured + unstructured
        if isinstance(arg, dict):
            title = arg.get("title") or arg.get("point") or ""
            description = arg.get("description") or arg.get("body") or ""
            content = f"{title}. {description}".strip()
        else:
            content = str(arg)

        if not content:
            continue

        embedding_vector = get_embedding(content)

        embedding_entry = ArgumentEmbedding(
            case_prep_id=case_prep.id,
            content=content,
            embedding=embedding_vector,
            argument_type="argument"
        )

        db.add(embedding_entry)

    db.commit()
    print("✅ Embeddings stored successfully!")