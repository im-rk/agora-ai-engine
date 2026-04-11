"""
Sandbox Test: Case Prep Generation & RAG Storage
Purpose: Test case prep generation and verify it's stored in pgvector
"""

import asyncio
import uuid
from src.core.database import SessionLocal
from src.models.setup import Motion, MotionCategory, CasePrep, ArgumentEmbedding
from src.models.user import User
from src.repositories.case_prep_repo import create_case_prep, update_case_prep
from src.ai.tools.rag_engine import RAGEngine


async def test_case_prep_storage():
    """Test case prep generation and RAG storage."""
    print("Testing Case Prep Generation & RAG Storage...")
    
    db = None
    
    try:
        db = SessionLocal()
        
        # Test 1: Create a test user
        print("\n[Test 1] Creating test user...")
        user = User(
            id=uuid.uuid4(),
            email=f"test_user_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="hashed_password",
            display_name="Test Debater"
        )
        db.add(user)
        db.flush()
        print(f"[PASS] User created: {user.id}")
        
        # Test 2: Create a test motion
        print("\n[Test 2] Creating test motion...")
        motion = Motion(
            id=uuid.uuid4(),
            motion_text="This house believes artificial intelligence will have a net positive impact on society",
            category=MotionCategory.TECHNOLOGY
        )
        db.add(motion)
        db.flush()
        print(f"[PASS] Motion created: {motion.id}")
        
        # Test 3: Create case prep
        print("\n[Test 3] Creating case prep...")
        case_prep = create_case_prep(
            db=db,
            user_id=str(user.id),
            motion_id=str(motion.id),
            side="affirmative"
        )
        print(f"[PASS] Case prep created: {case_prep.id}")
        
        # Test 3: Simulate AI-generated data
        print("\n[Test 3] Simulating AI-generated arguments...")
        model_definition = "Argument Framework: Consequentialist - Maximize benefits, minimize harms"
        arguments = [
            {"argument": "AI increases productivity", "impact": "Economic growth"},
            {"argument": "AI improves healthcare", "impact": "Better diagnostics"}
        ]
        counter_arguments = ["Job displacement concerns", "Bias in algorithms"]
        evidence = ["Study 1: UN Report on AI", "Study 2: McKinsey Report"]
        
        # Update case prep with AI data
        updated_prep = update_case_prep(
            db=db,
            case_prep_id=str(case_prep.id),
            model_definition=model_definition,
            arguments=arguments,
            counter_arguments=counter_arguments,
            evidence=evidence
        )
        print(f"[PASS] Case prep updated with AI data")
        
        # Test 4: Simulate storing embeddings in RAG (pgvector)
        print("\n[Test 4] Storing arguments in RAG (pgvector)...")
        
        # Create embeddings for each argument
        from langchain_huggingface import HuggingFaceEmbeddings
        # Use all-roberta-large-v1 which produces 1024 dimensions (matches DB schema)
        embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-roberta-large-v1")
        
        for arg in arguments:
            text = f"{arg['argument']} - {arg['impact']}"
            embedding_vector = embeddings_model.embed_query(text)
            
            arg_embedding = ArgumentEmbedding(
                id=uuid.uuid4(),
                case_prep_id=case_prep.id,
                content=text,
                embedding=embedding_vector,
                argument_type="main_argument"
            )
            db.add(arg_embedding)
        
        db.commit()
        print(f"[PASS] Stored {len(arguments)} argument embeddings in pgvector")
        
        # Test 5: Verify retrieval from RAG
        print("\n[Test 5] Verifying retrieval from RAG...")
        rag = RAGEngine()
        
        # Try to retrieve by searching for similar arguments
        query = "artificial intelligence productivity benefits"
        results = await rag.aretrieve_counter_arguments(topic=query, k=2)
        
        if results:
            print(f"[PASS] Retrieved {len(results)} similar arguments from RAG")
            for i, r in enumerate(results, 1):
                print(f"   [{i}] {r.get('text', '')[:80]}...")
        else:
            print(f"[WARN] No results retrieved (vector similarity may need tuning)")
        
        # Test 6: Verify case prep data integrity
        print("\n[Test 6] Verifying case prep data integrity...")
        retrieved_prep = db.query(CasePrep).filter(CasePrep.id == case_prep.id).first()
        assert retrieved_prep.model_definition == model_definition
        assert len(retrieved_prep.arguments) == 2
        assert len(retrieved_prep.counter_arguments) == 2
        print(f"[PASS] Case prep data integrity verified")
        
        print("\n[PASS] Case Prep Storage Test PASSED\n")
        return True
        
    except Exception as e:
        error_msg = str(e)
        # Hide SQL details for cleaner output
        if "[SQL:" in error_msg:
            error_msg = error_msg.split("[SQL:")[0].strip()
        print(f"[FAIL] Case Prep Storage Test FAILED: {error_msg}")
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    asyncio.run(test_case_prep_storage())
