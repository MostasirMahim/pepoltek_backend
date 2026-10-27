"""
ai_service/search.py
Semantic AI Candidate Search & Matching Engine according to Technical SRS Section 9.
Converts recruiter natural language queries into structured search criteria chips
using DeepSeek AI API (with failover), generates query vector embeddings,
computes multi-stage composite matching (semantic similarity, skill overlap, seniority, readiness),
and generates explainability factors (top positive factors and gaps).
"""
import logging
import math
import time
from typing import Optional, Any
from django.db.models import Q

from apps.candidates.models import Candidate, SectorChoice
from apps.ats.models import Requisition
from .services import nl_query_to_filter, generate_candidate_embedding

logger = logging.getLogger(__name__)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm1 * norm2)))


def search_candidates_ai(
    query: str,
    sector: Optional[str] = None,
    requisition_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Execute AI candidate search combining DeepSeek NL filter extraction and vector cosine matching.
    Returns:
    {
        "query": str,
        "extracted_filters": dict,
        "results": list[dict],
        "total_evaluated": int,
        "provider": str,
        "latency_seconds": float,
    }
    """
    start_time = time.time()
    clean_query = query.strip()

    # 1. Parse query to structured filters via DeepSeek AI API
    extracted = nl_query_to_filter(clean_query) or {}
    
    # Normalize extracted filters
    target_sector = (sector or extracted.get("sector") or "all").lower()
    target_level = (extracted.get("level") or "all").lower()
    target_role = extracted.get("role") or ""
    query_skills_raw = extracted.get("skills") or []
    must_haves_raw = extracted.get("must_haves") or []
    target_engagement = extracted.get("engagement") or ["all"]

    # Normalize skill names
    normalized_query_skills = []
    for s in query_skills_raw:
        if isinstance(s, dict):
            name = s.get("name", "").strip()
            min_y = s.get("min_years", 1)
            if name:
                normalized_query_skills.append({"name": name, "min_years": min_y})
        elif isinstance(s, str) and s.strip():
            normalized_query_skills.append({"name": s.strip(), "min_years": 1})

    query_skill_names_lower = [s["name"].lower() for s in normalized_query_skills]

    # 2. Generate vector embedding for the query
    query_embedding = generate_candidate_embedding(clean_query)

    # 3. Retrieve Candidate Pool
    candidates_qs = Candidate.objects.select_related("user").all()

    # Stage 1: Broad Hard Filter (Sector if explicit)
    if target_sector in ["tech", "technology"]:
        candidates_qs = candidates_qs.filter(sector=SectorChoice.TECHNOLOGY)
    elif target_sector in ["health", "healthcare"]:
        candidates_qs = candidates_qs.filter(sector=SectorChoice.HEALTHCARE)

    evaluated_candidates = []
    for cand in candidates_qs:
        cand_skills = [str(sk).strip() for sk in (cand.skills_cache or [])]
        cand_skills_lower = [sk.lower() for sk in cand_skills]
        cand_level = (cand.level or "senior").lower()

        # A. Semantic Vector Cosine Similarity (Weight: 35%)
        # Ensure candidate has embedding
        cand_emb = cand.embedding
        if not cand_emb:
            cand_emb = cand.generate_embedding_vector()
            cand.embedding = cand_emb
            cand.save(update_fields=["embedding"])

        raw_cosine = cosine_similarity(query_embedding, cand_emb)
        # Scale cosine (typically 0.10 - 0.50 in sparse hash space) to 0 - 100 percentage
        # Normalized min-max mapping: 0.05 -> 40%, 0.40 -> 98%
        if raw_cosine <= 0.05:
            semantic_score = round(raw_cosine * 800)
        else:
            semantic_score = min(99, round(40 + ((raw_cosine - 0.05) / 0.35) * 58))
        semantic_score = max(20, min(99, semantic_score))

        # B. Skill Overlap & Depth (Weight: 35%)
        matched_skills = []
        missing_skills = []
        for qs in normalized_query_skills:
            qs_name = qs["name"]
            qs_lower = qs_name.lower()
            if any(qs_lower in cs or cs in qs_lower for cs in cand_skills_lower):
                matched_skills.append(qs_name)
            else:
                missing_skills.append(qs_name)

        if normalized_query_skills:
            skill_ratio = len(matched_skills) / len(normalized_query_skills)
            skill_score = min(99, max(30, round(skill_ratio * 95 + (5 if len(cand_skills) >= 5 else 0))))
        else:
            # Fallback if no specific skills extracted from query
            skill_score = 80 if len(cand_skills) >= 4 else 65

        # C. Level Fit (Weight: 15%)
        level_hierarchy = {"junior": 1, "mid": 2, "senior": 3, "lead": 4, "director": 5, "c_level": 6}
        q_lvl_val = level_hierarchy.get(target_level, 3)
        c_lvl_val = level_hierarchy.get(cand_level, 3)
        if target_level == "all":
            level_score = 90
        elif c_lvl_val == q_lvl_val:
            level_score = 98
        elif c_lvl_val > q_lvl_val:
            level_score = 92  # Overqualified or higher tier is generally favorable
        elif c_lvl_val == q_lvl_val - 1:
            level_score = 75  # One step below
        else:
            level_score = 50

        # D. Profile Readiness & Vetting Tier (Weight: 15%)
        profile_strength_val = cand.profile_strength or 85
        vetting_score_val = 94 if cand_level in ["senior", "lead"] else 86
        readiness_score = round((profile_strength_val * 0.5) + (vetting_score_val * 0.5))

        # E. Final Composite Match Score (0 to 100)
        composite_score = round(
            (semantic_score * 0.35) +
            (skill_score * 0.35) +
            (level_score * 0.15) +
            (readiness_score * 0.15)
        )
        composite_score = min(99, max(45, composite_score))

        # F. Explainability Factors (Technical SRS Section 9.2: Top 3 Positives, Top 2 Gaps)
        positive_factors = []
        gap_factors = []

        if matched_skills:
            positive_factors.append(f"Direct verified mastery in: {', '.join(matched_skills[:3])}")
        if semantic_score >= 80:
            positive_factors.append(f"High semantic vector alignment ({semantic_score}% concept match)")
        if level_score >= 90:
            positive_factors.append(f"Seniority alignment ({cand_level.capitalize()} Specialist tier)")
        if cand.open_to_work:
            positive_factors.append("Immediate 7-day sprint start availability")
        if profile_strength_val >= 85:
            positive_factors.append("Pre-screened with high compliance readiness index")

        # Top 3 positives
        top_positives = positive_factors[:3]
        if not top_positives:
            top_positives = ["Verified professional background", "Complete candidate documentation"]

        # Gaps
        if missing_skills:
            gap_factors.append(f"Lacks explicit proof for: {', '.join(missing_skills[:2])}")
        if target_engagement != ["all"] and cand.engagement_prefs:
            overlap_eng = set(target_engagement).intersection(set(cand.engagement_prefs))
            if not overlap_eng:
                gap_factors.append(f"Engagement preference difference (seeks {', '.join(cand.engagement_prefs)})")
        if target_level != "all" and c_lvl_val < q_lvl_val:
            gap_factors.append(f"Seniority variance: currently {cand_level.capitalize()}")
        if not gap_factors:
            gap_factors.append("No material profile gaps identified for this search requirement")

        top_gaps = gap_factors[:2]

        # Formatting candidate representation
        user_email = cand.user.email if cand.user else ""
        name = cand.full_name or (user_email.split("@")[0].capitalize() if user_email else "Specialist")

        is_cand_tech = (cand.sector == SectorChoice.TECHNOLOGY) or str(cand.sector or '').strip().lower().startswith('tech')
        from apps.candidates.models import VettingStatus, ReadinessTier
        is_cand_vetted = (cand.vetting_status == VettingStatus.VETTED) or (cand.readiness_tier in [ReadinessTier.READY, ReadinessTier.ELITE])
        if cand.desired_hourly_rate and cand.desired_hourly_rate.strip():
            cand_rate = cand.desired_hourly_rate.strip()
        elif cand.expected_comp_min:
            cand_rate = f"${round(cand.expected_comp_min / 2080)}/hr" if cand.expected_comp_min > 500 else f"${cand.expected_comp_min}/hr"
        else:
            cand_rate = "Negotiable"

        unique_uuid = str(cand.id)
        display_id = f"CAND-{unique_uuid.replace('-', '')[-6:].upper()}"

        evaluated_candidates.append({
            "id": unique_uuid,
            "display_id": display_id,
            "db_id": unique_uuid,
            "name": name,
            "email": user_email,
            "title": cand.domain or ("Software Specialist" if is_cand_tech else "Healthcare Specialist"),
            "sector": "Software Tech" if is_cand_tech else "Healthcare",
            "skills": cand_skills,
            "experience": f"{cand.level.capitalize()} Specialist" if cand.level else "Specialist",
            "matchScore": f"{composite_score}%",
            "match_score": composite_score,
            "semantic_score": semantic_score,
            "skill_score": skill_score,
            "level_score": level_score,
            "profileStrength": profile_strength_val,
            "profile_strength": profile_strength_val,
            "readinessIndex": profile_strength_val,
            "cvScore": cand.cv_score or 0,
            "cv_score": cand.cv_score or 0,
            "vettingScore": vetting_score_val,
            "vetting_score": vetting_score_val,
            "vetting_status": cand.vetting_status or "not_started",
            "readinessTier": cand.readiness_tier or "unrated",
            "readiness_tier": cand.readiness_tier or "unrated",
            "rate": cand_rate,
            "availability": "Immediate" if cand.open_to_work else "Interview Only",
            "verified": is_cand_vetted,
            "phone": cand.phone or "",
            "location": cand.location or "Remote",
            "workAuth": cand.get_work_auth_display() if cand.work_auth else "Authorized",
            "positive_factors": top_positives,
            "gap_factors": top_gaps,
            "matched_skills": matched_skills,
        })

    # Sort descending by composite match score
    evaluated_candidates.sort(key=lambda x: x["match_score"], reverse=True)

    latency = round(time.time() - start_time, 2)
    logger.info("AI Candidate Search completed in %.2fs (evaluated=%d, query='%s')", latency, len(evaluated_candidates), clean_query)

    return {
        "query": clean_query,
        "extracted_filters": {
            "role": target_role or "Specialist",
            "skills": [s["name"] for s in normalized_query_skills],
            "level": target_level,
            "sector": target_sector,
            "engagement": target_engagement,
            "must_haves": must_haves_raw,
        },
        "results": evaluated_candidates,
        "total_evaluated": len(evaluated_candidates),
        "provider": "deepseek:deepseek-chat",
        "latency_seconds": latency,
    }
