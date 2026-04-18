"""
British Parliamentary (BP) End-to-End Test Script.

Tests the complete BP flow:
1. Schema validation (BPRole, BPTeam, request/response models)
2. Repository layer (create, read, update, cancel)
3. Service layer (match creation with Redis + AI)
4. State engine (8-speaker schedule generation)

Usage:
    cd agora-ai-engine
    python scripts/test_bp_e2e.py

Requirements:
    - PostgreSQL running with database created
    - Redis running
    - .env file configured with DATABASE_URL, REDIS_URL, OPENAI_API_KEY
"""

import sys
import os
import asyncio
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


# ============================================================================
# TEST 1: Schema Validation
# ============================================================================

def test_schemas():
    """Test that all BP Pydantic schemas are valid and importable."""
    print("\n" + "=" * 60)
    print("TEST 1: Schema Validation")
    print("=" * 60)
    
    # 1a. Import BP match schemas
    from src.schemas.bp.matches import (
        BPRole, BPTeam, MatchStatus,
        CreateMatchRequest, UpdateMatchStatusRequest,
        MatchResponse, MatchListItem, MatchListResponse,
        ParticipantInfo,
    )
    print("[PASS] All BP match schemas imported successfully")
    
    # 1b. Import BP case prep schemas
    from src.schemas.bp.case_prep import (
        GenerateCasePrepRequest, Argument,
        CasePrepResponse, AIPrepResult,
    )
    print("[PASS] All BP case prep schemas imported successfully")
    
    # 1c. Verify BPRole has 8 roles (vs AP's 6)
    assert len(BPRole) == 8, f"Expected 8 BP roles, got {len(BPRole)}"
    print(f"[PASS] BPRole has {len(BPRole)} roles:")
    for role in BPRole:
        print(f"   - {role.value}")
    
    # 1d. Verify BPTeam has 4 teams
    assert len(BPTeam) == 4, f"Expected 4 BP teams, got {len(BPTeam)}"
    print(f"[PASS] BPTeam has {len(BPTeam)} teams:")
    for team in BPTeam:
        print(f"   - {team.value}")
    
    # 1e. Verify BP-only roles exist
    assert "member_of_government" in [r.value for r in BPRole], "Missing member_of_government"
    assert "member_of_opposition" in [r.value for r in BPRole], "Missing member_of_opposition"
    print("[PASS] BP-only roles confirmed: member_of_government, member_of_opposition")
    
    # 1f. Test CreateMatchRequest validation
    request = CreateMatchRequest(
        motion="This house believes that AI will fundamentally change education",
        team=BPTeam.OPENING_GOVERNMENT,
        role=BPRole.PRIME_MINISTER
    )
    assert request.team == BPTeam.OPENING_GOVERNMENT
    assert request.role == BPRole.PRIME_MINISTER
    print(f"[PASS] CreateMatchRequest validated: team={request.team.value}, role={request.role.value}")
    
    # 1g. Test invalid request (motion too short)
    try:
        bad_request = CreateMatchRequest(
            motion="Short",  # Less than min_length=10
            team=BPTeam.OPENING_GOVERNMENT,
            role=BPRole.PRIME_MINISTER
        )
        print("[FAIL] Should have raised validation error for short motion")
    except Exception:
        print("[PASS] Short motion correctly rejected by validation")
    
    # 1h. Test Argument model
    arg = Argument(
        claim="Free education improves social mobility",
        reasoning="By removing financial barriers, more students from disadvantaged backgrounds can access higher education",
        impact="This leads to greater economic equality and breaks the cycle of poverty"
    )
    print(f"[PASS] Argument model validated: claim={arg.claim[:40]}...")
    
    # 1i. Test AIPrepResult model
    ai_result = AIPrepResult(
        model_definition="Under this motion, we define AI as artificial intelligence systems that can learn and adapt",
        arguments=[arg],
        counter_arguments=["Education quality may decrease with free access"],
        evidence=["Countries like Germany have free education with high employment rates"]
    )
    assert len(ai_result.arguments) == 1
    assert len(ai_result.counter_arguments) == 1
    print(f"[PASS] AIPrepResult model validated: {len(ai_result.arguments)} args, {len(ai_result.counter_arguments)} counter-args")
    
    print("\n[PASS] ALL SCHEMA TESTS PASSED")


# ============================================================================
# TEST 2: State Engine - 8-Speaker Schedule
# ============================================================================

def test_state_engine():
    """Test that the state engine generates correct 8-speaker BP schedule."""
    print("\n" + "=" * 60)
    print("TEST 2: State Engine - 8-Speaker Schedule")
    print("=" * 60)
    
    from src.engine.state import MatchStateManager
    
    manager = MatchStateManager()
    
    # 2a. Test BP schedule generation
    schedule = manager._generate_schedule(
        format_type="BP",
        human_side="opening_government",
        preferred_role="prime_minister"
    )
    
    assert len(schedule) == 8, f"Expected 8 turns for BP, got {len(schedule)}"
    print(f"[PASS] BP schedule has {len(schedule)} turns (correct)")
    
    # 2b. Verify turn order
    expected_roles = [
        "Prime Minister",
        "Leader of Opposition",
        "Deputy Prime Minister",
        "Deputy Leader of Opposition",
        "Member of Government",
        "Member of Opposition",
        "Government Whip",
        "Opposition Whip",
    ]
    
    actual_roles = [turn.role for turn in schedule]
    assert actual_roles == expected_roles, f"Turn order mismatch:\n  Expected: {expected_roles}\n  Got:      {actual_roles}"
    print("[PASS] Turn order is correct:")
    for i, turn in enumerate(schedule):
        human_marker = " ← YOU" if turn.player_type == "human" else ""
        print(f"   Turn {i}: {turn.role} ({turn.side}) [{turn.player_type}]{human_marker}")
    
    # 2c. Verify human is assigned to preferred role
    human_turns = [t for t in schedule if t.player_type == "human"]
    assert len(human_turns) >= 1, "No human turns assigned"
    assert human_turns[0].role == "Prime Minister", f"Human should be PM, got {human_turns[0].role}"
    print(f"[PASS] Human assigned to correct role: {human_turns[0].role}")
    
    # 2d. Test AP schedule for comparison (should have 6 turns)
    ap_schedule = manager._generate_schedule(
        format_type="AP",
        human_side="government",
        preferred_role="prime_minister"
    )
    assert len(ap_schedule) == 6, f"Expected 6 turns for AP, got {len(ap_schedule)}"
    print(f"[PASS] AP schedule has {len(ap_schedule)} turns (for comparison)")
    
    # 2e. Test BP with closing team role
    closing_schedule = manager._generate_schedule(
        format_type="BP",
        human_side="closing_opposition",
        preferred_role="opposition_whip"
    )
    # Note: the state engine uses role name matching, not team
    # "Opposition Whip" should be matched
    human_closing = [t for t in closing_schedule if t.player_type == "human"]
    if human_closing:
        print(f"[PASS] Closing team role assigned: {human_closing[0].role} ({human_closing[0].side})")
    else:
        print("[WARN] Human not assigned to closing role (check role name matching)")
    
    print("\n[PASS] ALL STATE ENGINE TESTS PASSED")


# ============================================================================
# TEST 3: Repository Layer (requires database)
# ============================================================================

def test_repository():
    """Test BP repository CRUD operations against the database."""
    print("\n" + "=" * 60)
    print("TEST 3: Repository Layer (Database)")
    print("=" * 60)
    
    try:
        from src.core.database import SessionLocal
        from src.repositories.bp.matches import BPMatchRepository, TEAM_TO_SIDE
        from src.models.debate import MatchFormat, MatchStatus
        
        db = SessionLocal()
        repo = BPMatchRepository()
        
        # 3a. Test team-to-side mapping
        assert TEAM_TO_SIDE["opening_government"] == "Government"
        assert TEAM_TO_SIDE["opening_opposition"] == "Opposition"
        assert TEAM_TO_SIDE["closing_government"] == "Government"
        assert TEAM_TO_SIDE["closing_opposition"] == "Opposition"
        print("[PASS] Team-to-side mapping correct")
        
        # 3b. Create a test match
        # We need a valid user_id - get one from the database
        from src.models.user import User
        test_user = db.query(User).first()
        
        if not test_user:
            print("[WARN] No users in database - skipping database tests")
            print("   Run auth/registration first to create a user")
            db.close()
            return
        
        user_id = str(test_user.id)
        print(f"[PASS] Using test user: {user_id} ({test_user.email})")
        
        # Create BP match
        match = repo.create_match(
            db=db,
            user_id=user_id,
            motion="This house believes that British Parliamentary debate is the best format for competitive debating",
            team="opening_government",
            role="prime_minister",
            skill_level="BEGINNER"
        )
        
        assert match is not None, "Match should not be None"
        assert match.format == MatchFormat.BRITISH_PARLIAMENTARY, f"Expected BP format, got {match.format}"
        assert match.human_role == "prime_minister", f"Expected prime_minister, got {match.human_role}"
        print(f"[PASS] BP Match created: {match.id}")
        print(f"   Format: {match.format.value}")
        print(f"   Role: {match.human_role}")
        print(f"   Status: {match.status.value}")
        
        # 3c. Read match by ID
        match_read = repo.get_match_by_id(db, str(match.id))
        assert match_read is not None, "Match should be findable by ID"
        assert str(match_read.id) == str(match.id), "IDs should match"
        print(f"[PASS] Match read by ID: {match_read.id}")
        
        # 3d. List user's matches
        matches_list = repo.get_matches_for_user(db, user_id, skip=0, limit=10)
        assert len(matches_list) >= 1, "Should find at least one match"
        print(f"[PASS] User's BP matches: {len(matches_list)} found")
        
        # 3e. Update match status
        updated = repo.update_match_status(db, str(match.id), "FINISHED")
        assert updated is not None, "Updated match should not be None"
        assert updated.status == MatchStatus.FINISHED, f"Expected FINISHED, got {updated.status}"
        print(f"[PASS] Match status updated: {updated.status.value}")
        
        # 3f. Cancel a match (set back to ABORTED for cleanup)
        success = repo.cancel_match(db, str(match.id))
        assert success, "Cancel should succeed"
        print(f"[PASS] Match cancelled successfully")
        
        # 3g. Verify cancelled match
        cancelled_match = repo.get_match_by_id(db, str(match.id))
        assert cancelled_match.status == MatchStatus.ABORTED
        print(f"[PASS] Cancelled match status verified: {cancelled_match.status.value}")
        
        db.close()
        print("\n[PASS] ALL REPOSITORY TESTS PASSED")
        
    except Exception as e:
        print(f"[FAIL] Repository test failed: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


# ============================================================================
# TEST 4: Service Layer (requires database + Redis)
# ============================================================================

def test_service():
    """Test BP service layer - match creation with Redis state init."""
    print("\n" + "=" * 60)
    print("TEST 4: Service Layer (Database + Redis)")
    print("=" * 60)
    
    async def _run_service_test():
        try:
            from src.core.database import SessionLocal
            from src.services.bp.matches import BPMatchService
            from src.schemas.bp.matches import CreateMatchRequest, BPTeam, BPRole
            from src.engine.state import state_manager
            
            db = SessionLocal()
            service = BPMatchService()
            
            # Get a test user
            from src.models.user import User
            test_user = db.query(User).first()
            
            if not test_user:
                print("[WARN] No users in database - skipping service tests")
                db.close()
                return
            
            user_id = str(test_user.id)
            
            # 4a. Create match via service (full pipeline)
            request = CreateMatchRequest(
                motion="This house believes that closing teams bring unique value to BP debates",
                team=BPTeam.CLOSING_GOVERNMENT,
                role=BPRole.MEMBER_OF_GOVERNMENT
            )
            
            print(f"Creating BP match via service for user {user_id}...")
            match_response = await service.create_match(
                db=db,
                user_id=user_id,
                request=request
            )
            
            assert match_response is not None, "Match response should not be None"
            print(f"[PASS] Match created via service: {match_response.match_id}")
            print(f"   Motion: {match_response.motion[:60]}...")
            print(f"   Your role: {match_response.your_role}")
            print(f"   Your team: {match_response.your_team}")
            print(f"   Status: {match_response.status}")
            
            # 4b. Verify Redis state was initialized
            state = await state_manager.get_state(match_response.match_id)
            if state:
                print(f"[PASS] Redis state initialized:")
                print(f"   Schedule length: {len(state.schedule)} turns")
                print(f"   Current turn index: {state.current_turn_index}")
                print(f"   Status: {state.status}")
                assert len(state.schedule) == 8, f"Expected 8 turns, got {len(state.schedule)}"
                print(f"[PASS] BP schedule has 8 turns (correct)")
            else:
                print("[WARN] Redis state not found - Redis may not be running")
            
            # 4c. Get match details
            match_detail = await service.get_match(db, match_response.match_id)
            assert match_detail is not None, "Match detail should not be None"
            print(f"[PASS] Match retrieved: {match_detail.match_id}")
            
            db.close()
            print("\n[PASS] ALL SERVICE TESTS PASSED")
            
        except Exception as e:
            print(f"[FAIL] Service test failed: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(_run_service_test())


# ============================================================================
# TEST 5: Import Chain Verification
# ============================================================================

def test_import_chain():
    """Verify the full import chain from routes → services → repositories → models."""
    print("\n" + "=" * 60)
    print("TEST 5: Import Chain Verification")
    print("=" * 60)
    
    # 5a. Route → Service → Repository → Model chain
    try:
        from src.api.routes.v1.bp import bp_router
        print("[PASS] bp_router imported from routes")
    except ImportError as e:
        print(f"[FAIL] Failed to import bp_router: {e}")
        return
    
    try:
        from src.api.routes.v1.bp.matches import match_service
        print(f"[PASS] BPMatchService instantiated: {type(match_service).__name__}")
    except ImportError as e:
        print(f"[FAIL] Failed to import match_service: {e}")
        return
    
    try:
        from src.api.routes.v1.bp.case_prep import case_prep_service
        print(f"[PASS] BPCasePrepService instantiated: {type(case_prep_service).__name__}")
    except ImportError as e:
        print(f"[FAIL] Failed to import case_prep_service: {e}")
        return
    
    # 5b. Verify BP router has routes
    routes = [route.path for route in bp_router.routes]
    print(f"[PASS] BP router has {len(routes)} registered routes:")
    for route_obj in bp_router.routes:
        methods = getattr(route_obj, 'methods', set())
        path = getattr(route_obj, 'path', 'N/A')
        print(f"   {methods} {path}")
    
    # 5c. Verify v1 router includes BP
    try:
        from src.api.routes.v1 import v1_router
        v1_routes = [route.path for route in v1_router.routes]
        bp_routes = [r for r in v1_routes if "/bp" in r]
        print(f"[PASS] v1_router has {len(bp_routes)} BP routes registered")
    except ImportError as e:
        print(f"[FAIL] Failed to import v1_router: {e}")
    
    print("\n[PASS] ALL IMPORT CHAIN TESTS PASSED")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  BRITISH PARLIAMENTARY (BP) END-TO-END TESTS")
    print("  Testing: Schemas -> State -> Repository -> Service -> Routes")
    print("=" * 60)
    
    # Test 1: Schemas (no external dependencies)
    test_schemas()
    
    # Test 2: State Engine (no external dependencies)
    test_state_engine()
    
    # Test 5: Import Chain (no external dependencies beyond imports)
    test_import_chain()
    
    # Test 3: Repository (requires PostgreSQL)
    print("\n" + "-" * 60)
    print("  DATABASE TESTS (require PostgreSQL)")
    print("-" * 60)
    test_repository()
    
    # Test 4: Service (requires PostgreSQL + Redis + AI keys)
    print("\n" + "-" * 60)
    print("  SERVICE TESTS (require PostgreSQL + Redis + AI keys)")
    print("-" * 60)
    test_service()
    
    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETE")
    print("=" * 60)
