"""
Integration test for Adjudication Pipeline.

Tests all 5 phases:
1. Macro-clash extraction
2. WCM matrix construction
3. WUDC pillar analysis
4. Speaker grading
5. Final summary

Run with: pytest tests/integration/api/adjudication/test_adjudication.py -v
"""

import pytest
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ============================================================================
# Sample Test Data
# ============================================================================

SAMPLE_TRANSCRIPT = """
Gov PM: Good evening. We are defining the motion as follows: "This House believes that AI should be regulated by government agencies rather than industry self-regulation. The key clash here is whether government can effectively regulate AI, or whether industry self-regulation is more responsive and innovative.

We have three main arguments today:
1. Government agencies have the institutional capacity and democratic mandate to regulate AI
2. Self-regulation has consistently failed in other industries (finance, pharma)
3. AI poses existential risks that require state intervention

Opp LO, your turn.

Opp LO: Thank you PM. We reject the government regulatory framework as inefficient and counterproductive. Our case:
1. Government moves slowly; AI innovation moves fast
2. Industry self-regulation through ethical boards is more nimble
3. Overregulation kills innovation and gives us a monopolistic tech landscape

Gov MG: The Opposition makes it sound like regulation and innovation are mutually exclusive. They're not. Europe's GDPR actually spurred innovation in privacy tech. We're not asking for draconian rules, just baseline standards that all companies follow.

Opp MG: But GDPR caused massive compliance costs that only big tech could afford. SMEs got crushed. This proves government regulation is a hidden tax on innovation.

Gov Reply: The motion isn't about perfect regulation. It's about whether government or industry should set the rules. Industry has financial incentives to cut corners on safety. Only government has the democratic accountability to enforce ethical standards.

Opp Reply: But government doesn't understand tech. They'll create rules that are obsolete in 6 months. Agile industry oversight is objectively faster. The real question is whether you trust tech companies to self-regulate—and empirically, they do when reputation is on the line.
"""

ADJUDICATION_REQUEST = {
    "transcript": SAMPLE_TRANSCRIPT,
    "debate_format": "AP",
    "speaker_roles": ["Gov PM", "Opp LO", "Gov MG", "Opp MG", "Gov Reply", "Opp Reply"],
    "session_id": "test-session-001"
}


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.asyncio
async def test_adjudication_endpoint():
    """Test POST /api/v1/ap/adjudications endpoint."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Validate structure
    assert "clashes" in result
    assert "wcm_matrix" in result
    assert "net_logic_score" in result
    assert "pillar_breakdown" in result
    assert "speaker_scores" in result
    assert "summary" in result


@pytest.mark.asyncio
async def test_macro_clash_extraction():
    """Test Phase 1: Macro-clash extraction."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    clashes = result["clashes"]
    
    # Should extract 3-5 macro-clashes
    assert 3 <= len(clashes) <= 5
    
    # Each clash should have these fields
    for clash in clashes:
        assert "id" in clash
        assert "theme" in clash
        assert "description" in clash
        assert "government_position" in clash
        assert "opposition_position" in clash


@pytest.mark.asyncio
async def test_wcm_matrix():
    """Test Phase 2: Weighted Clash Matrix."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    wcm = result["wcm_matrix"]
    
    # Should have entries for each clash
    assert len(wcm) >= 3
    
    # Validate WCM structure
    for entry in wcm:
        assert "clash_id" in entry
        assert "clash_theme" in entry
        assert 1 <= entry["weight"] <= 5
        assert -2 <= entry["delta"] <= 2
        assert "weighted_score" in entry
        assert entry["weighted_score"] == entry["weight"] * entry["delta"]


@pytest.mark.asyncio
async def test_pillar_breakdown():
    """Test Phase 3: WUDC Pillar Analysis."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    pillar = result["pillar_breakdown"]
    
    # Should have 4 pillars
    assert "matter" in pillar
    assert "manner" in pillar
    assert "method" in pillar
    assert "role" in pillar
    
    # Each pillar should have scores for both teams
    for pillar_name in ["matter", "manner", "method", "role"]:
        p = pillar[pillar_name]
        assert 0 <= p["government_score"] <= 25
        assert 0 <= p["opposition_score"] <= 25
        assert "reasoning" in p


@pytest.mark.asyncio
async def test_speaker_scores():
    """Test Phase 4: Speaker Grading."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    speakers = result["speaker_scores"]
    
    # Should have scores for all speakers
    assert len(speakers) >= 6
    
    # Validate speaker structure
    for speaker in speakers:
        assert "role" in speaker
        assert "side" in speaker
        assert speaker["side"] in ["Government", "Opposition"]
        assert 0 <= speaker["score"] <= 100
        assert 0 <= speaker["argument_quality"] <= 10
        assert 0 <= speaker["evidence_usage"] <= 10
        assert 0 <= speaker["responsiveness"] <= 10
        assert 0 <= speaker["structure"] <= 10
        assert 0 <= speaker["persona"] <= 10
        assert "feedback" in speaker


@pytest.mark.asyncio
async def test_summary():
    """Test Phase 5: Adjudication Summary."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    summary = result["summary"]
    
    # Should have adjudication statement and key decisions
    assert "adjudication" in summary
    assert len(summary["adjudication"]) > 50
    assert "key_decision_1" in summary
    assert "key_decision_2" in summary
    assert "key_decision_3" in summary


@pytest.mark.asyncio
async def test_verdict():
    """Test that verdict is correctly determined."""
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Should have a winning team
    assert "winning_team" in result
    assert result["winning_team"] in ["Government", "Opposition", "Tie"]
    
    # Should have scores for both teams
    assert "gov_total_score" in result
    assert "opp_total_score" in result
    assert 0 <= result["gov_total_score"] <= 100
    assert 0 <= result["opp_total_score"] <= 100


@pytest.mark.asyncio
async def test_invalid_request():
    """Test error handling for invalid requests."""
    
    # Test with too short transcript
    bad_request = {
        "transcript": "Too short",
        "debate_format": "AP",
        "speaker_roles": ["Gov PM", "Opp LO"],
        "session_id": "test"
    }
    
    response = client.post(
        "/api/v1/ap/adjudications",
        json=bad_request
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_cached_result():
    """Test retrieving cached adjudication result."""
    
    # First adjudicate
    response = client.post(
        "/api/v1/ap/adjudications",
        json=ADJUDICATION_REQUEST
    )
    
    assert response.status_code == 200
    
    # Try to retrieve cached result
    response = client.get(
        f"/api/v1/ap/adjudications/{ADJUDICATION_REQUEST['session_id']}"
    )
    
    # Should return cached result (may be None if not stored)
    assert response.status_code == 200
