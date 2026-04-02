# from src.ai.agents import generate_case_prep

# result = generate_case_prep(
#     motion="Ban AI in education",
#     side="Opposition",
#     skill_level="Beginner"
# )

# print(result)

from sqlalchemy import select
from src.core.database import SessionLocal

from src.ai.agents import generate_case_prep
from src.services.match_service import (
    create_case_prep,
    store_argument_embeddings
)

from src.models.user import User, SkillLevel
from src.models.setup import Motion, MotionCategory

import src.models  # IMPORTANT: registers all models
from src.core.database import Base, engine




# -------------------------------
# Helper: Get or Create User
# -------------------------------
def get_or_create_user(db):
    existing_user = db.execute(
        select(User).where(User.email == "test@test.com")
    ).scalars().first()

    if existing_user:
        print("👤 Using existing user")
        return existing_user

    user = User(
        email="test@test.com",
        password_hash="hashed_password",
        display_name="Test User",
        skill_level=SkillLevel.BEGINNER
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    print("👤 Created new user")
    return user


# -------------------------------
# Helper: Get or Create Motion
# -------------------------------
def get_or_create_motion(db):
    existing_motion = db.execute(
        select(Motion).where(Motion.motion_text == "Ban AI in education")
    ).scalars().first()

    if existing_motion:
        print("📌 Using existing motion")
        return existing_motion

    motion = Motion(
        motion_text="Ban AI in education",
        category=MotionCategory.TECHNOLOGY
    )
    db.add(motion)
    db.commit()
    db.refresh(motion)

    print("📌 Created new motion")
    return motion


# -------------------------------
# MAIN EXECUTION
# -------------------------------
def main():
    db = SessionLocal()

    try:
        # 1. Ensure user exists
        user = get_or_create_user(db)

        # 2. Ensure motion exists
        motion = get_or_create_motion(db)

        # 3. Generate AI case prep
        print("\n🧠 Generating AI Case Prep...\n")
        prep_data = generate_case_prep(
            motion=motion.motion_text,
            side="Opposition",
            skill_level=user.skill_level.value
        )

        print("✅ AI Generated Data:")
        print(prep_data)

        # 4. Save CasePrep
        print("\n💾 Saving CasePrep to DB...\n")
        case_prep,already_exists = create_case_prep(
            db=db,
            user_id=user.id,
            motion_id=motion.id,
            side="Opposition",
            prep_data=prep_data
        )

        print(f"🎉 CasePrep saved with ID: {case_prep.id}")

        if already_exists:
            print("⚠️ Skipping AI + Embeddings (already exists)")
            return

        # 5. Generate & Store Embeddings
        print("\n🧠 Generating and storing embeddings...\n")
        store_argument_embeddings(
            db=db,
            case_prep=case_prep,
            prep_data=prep_data
        )


    finally:
        db.close()


if __name__ == "__main__":
    main()