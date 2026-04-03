"""
Unit tests for debate engine rules (timers, turn orders, etc.).
These tests verify game logic without touching the database.
"""
import pytest


def test_ap_turn_order():
    """Test Asian Parliamentary format turn order."""
    # TODO: Import and test rules.get_turn_order("AP")
    expected_order = ["PM", "LO", "DPM", "DLO", "GW", "OW"]
    # assert rules.get_turn_order("AP") == expected_order
    pass


def test_bp_turn_order():
    """Test British Parliamentary format turn order."""
    # TODO: Import and test rules.get_turn_order("BP")
    expected_order = ["PM", "LO", "DPM", "DLO", "MG", "MO", "GW", "OW"]
    # assert rules.get_turn_order("BP") == expected_order
    pass


def test_speech_time_limits():
    """Test that speech time limits are correctly enforced."""
    # TODO: Test rules.get_speech_duration("PM") == 7 minutes
    pass


def test_poi_protection_period():
    """Test POI protection (first and last minute)."""
    # TODO: Test that POIs are not allowed in first/last minute
    pass
