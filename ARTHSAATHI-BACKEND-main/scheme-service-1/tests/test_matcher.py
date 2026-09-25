"""
Pytest test suite for scheme-service-1 matcher logic and API endpoints.
"""
from unittest.mock import patch
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.matcher import match_schemes
from app.schemas import UserProfile


def _create_sample_df(rows):
    """Helper to build a pandas DataFrame mirroring loaded CSV structure."""
    df = pd.DataFrame(rows)
    defaults = {
        "slug": "test-scheme",
        "name": "Test Scheme",
        "category": "Social welfare & Empowerment",
        "state": "Maharashtra",
        "description": "Test description",
        "benefits": "Test benefits",
        "apply_url": "http://example.com/apply",
        "official_url": "http://example.com/official",
        "apply_url_clean": "http://example.com/apply",
        "eligibility_gender": "all",
        "eligibility_age_min": None,
        "eligibility_age_max": None,
        "eligibility_caste": [],
        "eligibility_caste_extended": [],
        "eligibility_income_max": None,
        "eligibility_residence": "both",
        "eligibility_state": [],
        "eligibility_disability": None,
        "eligibility_bpl": None,
        "eligibility_minority": None,
        "eligibility_student": None,
        "beneficiary_type": "",
        "has_structured_eligibility": True,
    }
    for col, default_val in defaults.items():
        if col not in df.columns:
            df[col] = [default_val] * len(df)
    return df


def test_bpl_low_income_matching():
    """
    Test 1: Profile with BPL=True, low income, matching state/gender/age against a known-eligible synthetic scheme row.
    Confirm it's included and scored higher than a non-matching one.
    """
    profile = UserProfile(
        gender="female",
        age=25,
        state="Maharashtra",
        residence="rural",
        caste="OBC",
        disability=False,
        minority=False,
        is_student=False,
        bpl=True,
        annual_income=50000,
    )

    matching_row = {
        "slug": "matching-scheme",
        "name": "Matching BPL Scheme",
        "category": "Social welfare & Empowerment",
        "state": "Maharashtra",
        "eligibility_gender": "female",
        "eligibility_age_min": 18,
        "eligibility_age_max": 50,
        "eligibility_residence": "rural",
        "eligibility_state": ["Maharashtra"],
        "eligibility_caste_extended": ["OBC"],
        "eligibility_bpl": True,
        "eligibility_income_max": 100000,
        "has_structured_eligibility": True,
    }

    generic_row = {
        "slug": "generic-scheme",
        "name": "Generic Scheme",
        "category": "General",
        "state": "Central",
        "eligibility_gender": "all",
        "eligibility_residence": "both",
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([matching_row, generic_row])
    results = match_schemes(profile, df)

    assert len(results) == 2
    assert results[0].slug == "matching-scheme"
    assert results[0].match_score > results[1].match_score
    assert "BPL match" in results[0].matched_criteria
    assert "income eligible" in results[0].matched_criteria


def test_hard_excluded_by_age():
    """
    Test 2: Profile that should be hard-excluded by age (too young/old for a scheme with has_structured_eligibility=True).
    Confirm it's excluded.
    """
    profile = UserProfile(
        gender="male",
        age=12,  # Too young
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=True,
        bpl=False,
        annual_income=200000,
    )

    row = {
        "slug": "adult-scheme",
        "name": "Adult Scheme",
        "eligibility_age_min": 18,
        "eligibility_age_max": 60,
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([row])
    results = match_schemes(profile, df)

    assert len(results) == 0


def test_unstructured_eligibility_included():
    """
    Test 3: A row with has_structured_eligibility=False.
    Confirm it's included regardless of hard filters failing (e.g. age), and match_confidence == 'medium'.
    """
    profile = UserProfile(
        gender="male",
        age=70,  # Fails age min/max, but row has has_structured_eligibility=False
        state="Karnataka",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=500000,
    )

    row = {
        "slug": "unstructured-scheme",
        "name": "Unstructured Scheme",
        "state": "Karnataka",
        "eligibility_age_min": 18,
        "eligibility_age_max": 50,
        "has_structured_eligibility": False,
    }

    df = _create_sample_df([row])
    results = match_schemes(profile, df)

    assert len(results) == 1
    assert results[0].slug == "unstructured-scheme"
    assert results[0].match_confidence == "medium"


def test_minority_soft_boost():
    """
    Test 4: Minority soft-boost: same profile with minority=True vs minority=False against a scheme with eligibility_minority=True.
    Confirm the True case scores higher, neither is excluded.
    """
    minority_profile = UserProfile(
        gender="female",
        age=30,
        state="Delhi",
        residence="urban",
        caste="General",
        disability=False,
        minority=True,
        is_student=False,
        bpl=False,
        annual_income=300000,
    )

    non_minority_profile = UserProfile(
        gender="female",
        age=30,
        state="Delhi",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=300000,
    )

    row = {
        "slug": "minority-scheme",
        "name": "Minority Scheme",
        "state": "Delhi",
        "eligibility_minority": True,
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([row])

    minority_results = match_schemes(minority_profile, df)
    non_minority_results = match_schemes(non_minority_profile, df)

    assert len(minority_results) == 1
    assert len(non_minority_results) == 1
    assert minority_results[0].match_score > non_minority_results[0].match_score
    assert "minority boost" in minority_results[0].matched_criteria


def test_caste_exclusion():
    """
    Test 5: Caste exclusion: profile with caste="General" against a scheme whose eligibility_caste_extended=["SC"] and has_structured_eligibility=True.
    Confirm excluded.
    """
    profile = UserProfile(
        gender="male",
        age=25,
        state="Central",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=100000,
    )

    row = {
        "slug": "sc-only-scheme",
        "name": "SC Only Scheme",
        "state": "Central",
        "eligibility_caste_extended": ["SC"],
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([row])
    results = match_schemes(profile, df)

    assert len(results) == 0


def test_health_endpoint():
    """
    Test 6: /health endpoint returns schemes_loaded > 0.
    Mocks load_schemes to return sample DataFrame.
    """
    sample_df = _create_sample_df([{"slug": "s1"}, {"slug": "s2"}])
    with patch("app.main.load_schemes", return_value=sample_df):
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["schemes_loaded"] > 0


def test_state_hard_exclusion_regardless_of_structured_flag():
    """
    Test 7: Synthetic row with has_structured_eligibility=False and state="Kerala",
    run a Maharashtra profile against it, assert it's excluded.
    """
    profile = UserProfile(
        gender="female",
        age=30,
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=200000,
    )

    row = {
        "slug": "kerala-scheme",
        "name": "Kerala Scheme",
        "state": "Kerala",
        "has_structured_eligibility": False,
    }

    df = _create_sample_df([row])
    results = match_schemes(profile, df)

    assert len(results) == 0


def test_family_soft_boost():
    """
    Test 8: Family soft-boost: mirror test_minority_soft_boost.
    Build a synthetic row with beneficiary_type="Family", run the same profile once with applying_for_family=False and once with applying_for_family=True, assert the True case scores 15 points higher and neither run excludes the row.
    """
    family_profile = UserProfile(
        gender="female",
        age=30,
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=300000,
        applying_for_family=True,
    )

    individual_profile = UserProfile(
        gender="female",
        age=30,
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=300000,
        applying_for_family=False,
    )

    row = {
        "slug": "family-scheme",
        "name": "Family Scheme",
        "state": "Maharashtra",
        "beneficiary_type": "Family",
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([row])

    family_results = match_schemes(family_profile, df)
    individual_results = match_schemes(individual_profile, df)

    assert len(family_results) == 1
    assert len(individual_results) == 1
    assert family_results[0].match_score == individual_results[0].match_score + 15.0
    assert "family scheme" in family_results[0].matched_criteria


def test_student_scholarship_excluded_for_non_student():
    """
    Test 9: Scheme with eligibility_student=True or student scholarship in text
    must be excluded for profile with is_student=False.
    """
    non_student = UserProfile(
        gender="male",
        age=30,
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=600000,
    )

    student_row = {
        "slug": "post-matric-scholarship",
        "name": "Post-Matric Scholarship for College Students",
        "state": "Maharashtra",
        "eligibility_student": True,
        "has_structured_eligibility": True,
    }

    df = _create_sample_df([student_row])
    results = match_schemes(non_student, df)
    assert len(results) == 0


def test_farming_excluded_for_urban_salaried():
    """
    Test 10: Agriculture / farmer scheme must be excluded for urban salaried user.
    """
    urban_user = UserProfile(
        gender="male",
        age=28,
        state="Maharashtra",
        residence="urban",
        caste="General",
        disability=False,
        minority=False,
        is_student=False,
        bpl=False,
        annual_income=700000,
        occupation="Software Engineer",
        occupation_type="SALARIED",
    )

    farm_row = {
        "slug": "farm-pond-scheme",
        "name": "Chief Minister Sustainable Agriculture Farm Pond Scheme for Shetkari",
        "category": "Agriculture,Rural & Environment",
        "state": "Maharashtra",
        "has_structured_eligibility": False,
    }

    df = _create_sample_df([farm_row])
    results = match_schemes(urban_user, df)
    assert len(results) == 0



