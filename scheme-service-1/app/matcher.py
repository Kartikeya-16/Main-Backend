"""
Scheme matching engine for Government Scheme Generator microservice.

Contains filtering and scoring logic for user profiles against loaded scheme dataset.
Provides strict compatibility checks to prevent irrelevant schemes (e.g. student allowances
for non-students, farmer subsidies for urban professionals, minority-exclusive loans for non-minorities)
from being recommended.
"""
import json
import logging
from typing import Any, List, Optional
import pandas as pd
from app.schemas import MatchedScheme, UserProfile

logger = logging.getLogger("scheme-service.matcher")

INDIAN_STATES = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "delhi", "jammu and kashmir", "jammu & kashmir", "ladakh"
]

NE_STATES = {
    "assam", "meghalaya", "manipur", "mizoram",
    "nagaland", "tripura", "arunachal pradesh", "sikkim"
}


def _safe_bool_val(val: Any) -> Optional[bool]:
    """Helper to cleanly resolve bool from row values."""
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _is_category_relevant(category_str: str, profile: UserProfile) -> bool:
    """Check if category text contains tokens relevant to the user profile."""
    if not category_str:
        return False

    cat_lower = category_str.lower()
    occ_type = (profile.occupation_type or "").lower()

    if profile.is_student and any(tok in cat_lower for tok in ["education", "learning", "student", "skill"]):
        return True
    if profile.bpl and any(tok in cat_lower for tok in ["welfare", "empowerment", "poverty", "housing", "social"]):
        return True
    if profile.disability and any(tok in cat_lower for tok in ["disability", "rehabilitation", "special"]):
        return True
    if profile.minority and "minority" in cat_lower:
        return True
    if (profile.residence == "urban" or occ_type in ("salaried", "business")) and any(
        tok in cat_lower for tok in ["business", "banking", "financial", "employment", "housing", "skills", "science", "it"]
    ):
        return True
    return False


def is_scheme_incompatible(row: Any, profile: UserProfile) -> bool:
    """
    Checks if a scheme has strong textual / metadata indicators that make it
    completely irrelevant or ineligible for this specific user profile.
    """
    combined_text = " ".join([
        str(row.get("name", "")),
        str(row.get("description", "")),
        str(row.get("eligibility_text", "")),
        str(row.get("tags", "")),
        str(row.get("category", "")),
        str(row.get("ministry", "")),
        str(row.get("department", "")),
    ]).lower()

    # 1. Non-individual institutions (NGOs, hospitals, universities, industries)
    b_type = str(row.get("beneficiary_type", "")).strip().lower()
    occ_type = (profile.occupation_type or "").lower()
    if b_type and not any(k in b_type for k in ["individual", "family", "student", "all", "nan"]):
        if occ_type != "business" and not any(k in b_type for k in ["individual", "family"]):
            if any(k in b_type for k in ["institution", "ngo", "hospital", "university", "societies", "industries", "gram panchayat"]):
                return True

    # 2. Regional / State restrictions embedded in scheme name
    p_state = (profile.state or "").strip().lower()
    if p_state and p_state not in NE_STATES and any(
        k in combined_text for k in ["north eastern region", "in north east", "for ner", "north eastern states"]
    ):
        return True
    if p_state and p_state not in ("jammu and kashmir", "jammu & kashmir", "ladakh") and any(
        k in combined_text for k in ["jammu & kashmir", "jammu and kashmir", "union territory of ladakh"]
    ):
        return True

    # 3. BPL exclusivity for higher-income individuals (income >= 3 Lakhs)
    if profile.annual_income and profile.annual_income >= 300000:
        if _safe_bool_val(row.get("eligibility_bpl")) is True:
            return True
        if any(kw in combined_text for kw in [
            "bpl card holder", "below poverty line (bpl)", "antyodaya anna",
            "yellow ration card", "income should be below ₹98,000", "income below 1,00,000",
            "income below 1,20,000", "bpl family", "bpl families"
        ]):
            return True

    # 4. Minority exclusivity: exclude specifically restricted minority programs (e.g. NMDFC, Waqf)
    if not profile.minority:
        if any(kw in combined_text for kw in [
            "nmdfc", "national minorities development and finance",
            "for minority communities only", "only for minority", "only for minorities",
            "minority community only", "waqf board"
        ]):
            return True

    # 7. Student exclusivity: exclude student scholarships/hostels for non-students
    if not profile.is_student:
        if _safe_bool_val(row.get("eligibility_student")) is True:
            return True
        if any(kw in combined_text for kw in [
            "bonafide student", "post-matric scholarship", "pre-matric scholarship",
            "hostel maintenance allowance", "school student", "college student",
            "tuition fee waiver", "fellowship for students", "enrolled in class",
            "studying in class", "admitted in school", "admitted in college",
            "scholarship scheme", "scholarship for"
        ]):
            return True

    # 8. Disability exclusivity: exclude disability grants for non-disabled users
    if not profile.disability:
        if _safe_bool_val(row.get("eligibility_disability")) is True:
            return True
        if any(kw in combined_text for kw in [
            "divyang", "disability pension", "handicapped", "visually impaired",
            "locomotor disability", "hearing impaired", "mental retardation",
            "40% disability", "disability certificate", "prosthetic aids"
        ]):
            return True

    # 9. Gender exclusivity
    e_gender = str(row.get("eligibility_gender", "all")).strip().lower()
    if profile.gender != "transgender":
        if "transgender" in e_gender:
            return True
        if any(kw in combined_text for kw in [
            "transgender person", "transgender persons", "garima greh", "third gender"
        ]):
            return True

    if profile.gender == "male":
        if e_gender in ("female", "women"):
            return True
        if any(kw in combined_text for kw in [
            "widow pension", "destitute widow", "single mother", "mahila vikas",
            "pregnant and lactating", "maternity benefit to mother", "girl child",
            "only for women", "women entrepreneurs only", "women only", "girls only",
            "sukanya samriddhi", "maternity benefit"
        ]):
            return True
    elif profile.gender == "female":
        if e_gender == "male":
            return True

    # 10. Caste exclusivity
    e_caste_ext = row.get("eligibility_caste_extended", [])
    if isinstance(e_caste_ext, str):
        try:
            e_caste_ext = json.loads(e_caste_ext.replace("'", '"'))
        except Exception:
            e_caste_ext = []
    if isinstance(e_caste_ext, list) and len(e_caste_ext) > 0:
        if profile.caste not in e_caste_ext:
            return True

    if profile.caste == "General":
        if any(kw in combined_text for kw in [
            "scheduled caste", "scheduled tribe", "special component plan",
            "tribal sub plan", "charmakar", "matang", "valmiki", "safai karamchari",
            "nsfdc", "nstfdc", "sc co-op", "self help group of sc", "tribal affairs",
            "obc only", "sc only", "st only", "vjnt", "nomadic tribe", "denotified tribe", "pvtg"
        ]):
            return True
    elif profile.caste == "OBC":
        if any(kw in combined_text for kw in [
            "scheduled caste", "scheduled tribe", "sc only", "st only",
            "nsfdc", "nstfdc", "tribal affairs"
        ]):
            return True

    # 11. Residence exclusivity
    if profile.residence == "urban":
        if str(row.get("eligibility_residence", "")).lower() == "rural":
            return True
        if any(kw in combined_text for kw in [
            "rural livelihoods mission", "nrlm", "rural areas only", "rural youth only", "rural families only"
        ]):
            return True
    elif profile.residence == "rural":
        if str(row.get("eligibility_residence", "")).lower() == "urban":
            return True

    # 12. Occupation and livelihood exclusivity
    occ_str = (profile.occupation or "").lower()
    is_farmer = any(w in occ_str for w in ["farmer", "kisan", "agriculture", "cultivator", "agri", "horticulture"])
    is_manual_worker = any(w in occ_str for w in ["construction", "labor", "worker", "carpenter", "mason", "coolie"])
    is_artisan = any(w in occ_str for w in ["weaver", "artisan", "coir", "potter", "handicraft", "craftsman"])
    is_defense = any(w in occ_str for w in ["defense", "army", "navy", "air force", "military", "ex-servicemen"])
    is_teacher = any(w in occ_str for w in ["teacher", "professor", "faculty", "lecturer", "librarian"])

    if not is_defense and any(kw in combined_text for kw in [
        "ex-servicemen", "non pensioner ex-servicemen", "war widow", "affdf", "gallantry award"
    ]):
        return True

    if not is_teacher and any(kw in combined_text for kw in [
        "for teachers", "for librarians", "for technical teachers", "training of technical teachers", "aicte-"
    ]):
        return True

    if not is_farmer and (profile.residence == "urban" or occ_type in ("salaried", "business")):
        cats = [c.strip() for c in str(row.get("category", "")).split(",")]
        if all(c in ["Agriculture", "Rural & Environment", "Agriculture,Rural & Environment"] for c in cats):
            return True
        if any(kw in combined_text for kw in [
            "kisan", "shetkari", "crop insurance", "farm pond", "fertilizer subsidy",
            "mini tractor", "tractor", "agricultural implements", "livestock",
            "dairy farmer", "perennial fruit crop", "milch animals",
            "fodder development", "horticulture plantation", "seed subsidy",
            "krishi sinchayee", "soil health card", "coconut palm insurance", "kera suraksha",
            "pm-kisan", "pm kisan", "kisan credit card", "kisan pension", "kisan maandhan"
        ]):
            return True

    if not is_manual_worker and any(kw in combined_text for kw in [
        "construction worker", "registered worker of bocw", "bocw", "building and other construction",
        "safai karamchari", "safai", "manual scavenger", "sanitation worker", "headload worker", "coolie"
    ]):
        return True

    if not is_artisan and occ_type == "salaried":
        if any(kw in combined_text for kw in [
            "coir", "powerloom", "handloom", "weaver", "weavers", "khadi", "beedi",
            "toddy tapper", "rubber plantation", "rubber tapper", "tappers in small rubber",
            "fisherman", "fishermen", "fisher", "fish farmer", "matsya sampada", "matsya",
            "potters", "potter", "blacksmith", "tea plantation", "sericulture"
        ]):
            return True

    # 13. Exclude pure academic research/scientific awards from citizen welfare
    if any(kw in combined_text for kw in [
        "foundation award", "memorial award", "scientific award", "young scientist", "national award for"
    ]):
        return True

    # 14. Senior citizen pension exclusivity for youth
    if profile.age < 55:
        if any(kw in combined_text for kw in [
            "old age pension", "vridha pension", "senior citizen pension",
            "60 years of age or above", "aged 60 and above", "indira gandhi national old age"
        ]):
            return True

    return False


def passes_state_filter(row: Any, profile_state: Optional[str]) -> bool:
    """Checks if a scheme passes state eligibility unconditionally."""
    row_state = str(row.get("state", "Central")).strip()
    if not profile_state or not str(profile_state).strip():
        return True  # no state given by user -> don't exclude on geography

    p_state = str(profile_state).strip().lower()

    if row_state.lower() != "central" and row_state.lower() != p_state:
        e_state = row.get("eligibility_state", [])
        if not (isinstance(e_state, list) and any(p_state == str(s).strip().lower() for s in e_state)):
            return False

    # Check for state exclusivity embedded in scheme name (e.g. "in Assam", "of Bihar")
    name_lower = str(row.get("name", "")).lower()
    for st in INDIAN_STATES:
        if st != p_state:
            if (
                f"in {st}" in name_lower
                or f"of {st}" in name_lower
                or f"for {st}" in name_lower
                or f"{st} government" in name_lower
            ):
                return False

    return True


def match_schemes(profile: UserProfile, df: pd.DataFrame, limit: int = 20) -> List[MatchedScheme]:
    """
    Match a UserProfile against the scheme dataset.

    - Enforces state filtering unconditionally for all schemes.
    - Filters out schemes with mutually incompatible criteria.
    - Applies hard filters (age, caste, income, disability, bpl) on populated fields.
    - Applies soft scoring (+15 affinity boosts, +10 category relevance).
    - Assigns match confidence ("high" vs "medium" vs "low").
    - Returns top `limit` schemes sorted by match_score descending.
    """
    results: List[MatchedScheme] = []

    if df.empty:
        return results

    if profile.gender == "transgender":
        logger.info("Transgender gender specified: treating as matching all gender filters due to dataset limitation.")

    occ_type = (profile.occupation_type or "").lower()
    occ_str = (profile.occupation or "").lower()

    for _, row in df.iterrows():
        # Unconditional state filter check
        if not passes_state_filter(row, profile.state):
            continue

        # Incompatibility check to eliminate irrelevant schemes
        if is_scheme_incompatible(row, profile):
            continue

        has_structured = _safe_bool_val(row.get("has_structured_eligibility")) is True

        # Extract values for filters and scoring
        e_gender = str(row.get("eligibility_gender", "all")).strip().lower()
        min_age = row.get("eligibility_age_min")
        max_age = row.get("eligibility_age_max")
        e_residence = str(row.get("eligibility_residence", "both")).strip().lower()
        e_caste_ext = row.get("eligibility_caste_extended", [])
        if isinstance(e_caste_ext, str):
            try:
                e_caste_ext = json.loads(e_caste_ext.replace("'", '"'))
            except Exception:
                e_caste_ext = []
        e_income_max = row.get("eligibility_income_max")
        e_disability = _safe_bool_val(row.get("eligibility_disability"))
        e_bpl = _safe_bool_val(row.get("eligibility_bpl"))
        e_minority = _safe_bool_val(row.get("eligibility_minority"))
        e_student = _safe_bool_val(row.get("eligibility_student"))

        # -------------------------------------------------------------
        # Hard Filters (ONLY enforced when has_structured_eligibility is True)
        # -------------------------------------------------------------
        if has_structured:
            # Gender filter
            if profile.gender != "transgender" and e_gender not in ("all", profile.gender):
                continue

            # Age filter
            if pd.notna(min_age) and min_age is not None:
                if profile.age < float(min_age):
                    continue
            if pd.notna(max_age) and max_age is not None:
                if profile.age > float(max_age):
                    continue

            # Residence filter
            if e_residence == "urban" and profile.residence == "rural":
                continue
            if e_residence == "rural" and profile.residence == "urban":
                continue

            # Caste filter
            if isinstance(e_caste_ext, list) and len(e_caste_ext) > 0:
                if profile.caste not in e_caste_ext:
                    continue

            # Income filter
            if pd.notna(e_income_max) and e_income_max is not None and profile.annual_income is not None:
                if profile.annual_income > float(e_income_max):
                    continue

            # Disability filter
            if e_disability is True and profile.disability is False:
                continue

            # BPL filter
            if e_bpl is True and profile.bpl is False:
                continue

        # -------------------------------------------------------------
        # Scoring Evaluation
        # -------------------------------------------------------------
        score = 40.0
        criteria: List[str] = []
        has_non_trivial_hard_match = False

        # Gender scoring
        if e_gender in ("male", "female") and e_gender == profile.gender:
            score += 10.0
            criteria.append(f"gender: {profile.gender}")
            has_non_trivial_hard_match = True
        elif e_gender == "all":
            score += 4.0

        # Age scoring
        if (pd.notna(min_age) and min_age is not None) or (pd.notna(max_age) and max_age is not None):
            score += 10.0
            criteria.append("age eligible")
            has_non_trivial_hard_match = True

        # Residence scoring
        if e_residence in ("urban", "rural") and e_residence == profile.residence:
            score += 10.0
            criteria.append(f"residence: {profile.residence}")
            has_non_trivial_hard_match = True
        elif e_residence == "both":
            score += 3.0

        # State scoring
        e_state = row.get("eligibility_state", [])
        row_state = str(row.get("state", "Central")).strip()
        if profile.state and (
            row_state.lower() == profile.state.lower()
            or (isinstance(e_state, list) and any(profile.state.lower() == str(s).lower() for s in e_state))
        ):
            score += 16.0
            criteria.append(f"state: {profile.state}")
            has_non_trivial_hard_match = True
        elif row_state.lower() == "central":
            score += 8.0
            criteria.append("state: Central")

        # Caste scoring
        if isinstance(e_caste_ext, list) and len(e_caste_ext) > 0 and any(profile.caste.lower() == str(c).lower() for c in e_caste_ext):
            score += 14.0
            criteria.append(f"caste: {profile.caste}")
            has_non_trivial_hard_match = True

        # Income scoring
        if pd.notna(e_income_max) and e_income_max is not None and profile.annual_income is not None:
            if profile.annual_income <= float(e_income_max):
                score += 10.0
                criteria.append("income eligible")
                has_non_trivial_hard_match = True

        # Demographic boosts
        if profile.disability and e_disability is True:
            score += 15.0
            criteria.append("disability match")
            has_non_trivial_hard_match = True

        if profile.bpl and e_bpl is True:
            score += 15.0
            criteria.append("BPL match")
            has_non_trivial_hard_match = True

        if profile.minority and e_minority is True:
            score += 15.0
            criteria.append("minority boost")
            has_non_trivial_hard_match = True

        if profile.is_student and e_student is True:
            score += 15.0
            criteria.append("student boost")
            has_non_trivial_hard_match = True

        if profile.applying_for_family and "family" in str(row.get("beneficiary_type", "")).lower():
            score += 15.0
            criteria.append("family scheme")

        # Occupation & Life Stage Affinity Boosts
        combined_scheme_text = (
            str(row.get("name", "")) + " " +
            str(row.get("description", "")) + " " +
            str(row.get("category", ""))
        ).lower()

        if occ_type == "salaried" or "software" in occ_str or "engineer" in occ_str:
            if any(k in combined_scheme_text for k in [
                "pension", "insurance", "financial services", "banking", "epfo",
                "beemit vyakti", "provident fund", "middle income", "housing", "urban",
                "pradhan mantri awas", "skill development", "prior learning"
            ]):
                score += 15.0
                criteria.append("salaried professional match")

        elif occ_type == "business":
            if any(k in combined_scheme_text for k in [
                "msme", "credit guarantee", "entrepreneur", "startup", "mudra",
                "stand up india", "business loan", "cmegp", "pmegp"
            ]):
                score += 15.0
                criteria.append("business / entrepreneur match")

        elif profile.is_student:
            if any(k in combined_scheme_text for k in ["scholarship", "education", "learning", "skill", "fellowship"]):
                score += 15.0
                criteria.append("student education match")

        # Category relevance boost
        cat_str = str(row.get("category", ""))
        if _is_category_relevant(cat_str, profile):
            score += 10.0
            criteria.append("category match")

        # Confidence assignment
        if has_structured and has_non_trivial_hard_match:
            confidence = "high"
        else:
            confidence = "medium"

        # URLs handling
        apply_url_val = row.get("apply_url_clean")
        if pd.isna(apply_url_val) or not str(apply_url_val).strip():
            apply_url_val = row.get("apply_url")
        if pd.isna(apply_url_val) or not str(apply_url_val).strip():
            apply_url_clean = None
        else:
            apply_url_clean = str(apply_url_val).strip()

        official_url_val = row.get("official_url")
        if pd.isna(official_url_val) or not str(official_url_val).strip():
            official_url_clean = None
        else:
            official_url_clean = str(official_url_val).strip()

        docs_val = row.get("documents_required")
        docs_clean = str(docs_val).strip() if pd.notna(docs_val) and str(docs_val).strip() else None

        app_proc_val = row.get("application_process")
        app_proc_clean = str(app_proc_val).strip() if pd.notna(app_proc_val) and str(app_proc_val).strip() else None

        elig_text_val = row.get("eligibility_text")
        elig_text_clean = str(elig_text_val).strip() if pd.notna(elig_text_val) and str(elig_text_val).strip() else None

        min_val = row.get("ministry")
        min_clean = str(min_val).strip() if pd.notna(min_val) and str(min_val).strip() else None

        dept_val = row.get("department")
        dept_clean = str(dept_val).strip() if pd.notna(dept_val) and str(dept_val).strip() else None

        final_score = min(round(score, 1), 98.0) if score < 100 else 100.0

        scheme = MatchedScheme(
            slug=str(row.get("slug", "")),
            name=str(row.get("name", "")),
            category=cat_str,
            state=row_state,
            description=str(row.get("description", "")),
            benefits=str(row.get("benefits", "")),
            apply_url=apply_url_clean,
            official_url=official_url_clean,
            match_score=final_score,
            match_confidence=confidence,
            matched_criteria=criteria,
            documents_required=docs_clean,
            application_process=app_proc_clean,
            eligibility_text=elig_text_clean,
            ministry=min_clean,
            department=dept_clean,
            beneficiary_type=str(row.get("beneficiary_type", "")).strip() if pd.notna(row.get("beneficiary_type")) else None,
            tags=str(row.get("tags", "")).strip() if pd.notna(row.get("tags")) else None,
        )
        results.append(scheme)

    # Sort results by match_score descending
    results.sort(key=lambda x: x.match_score, reverse=True)
    return results[:limit]
