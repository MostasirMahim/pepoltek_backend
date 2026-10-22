"""
config_center/selectors.py
Read-only selectors for platform configuration, hiring rules, and candidate taxonomies.
Strict House Style Rule: Zero em dashes or en dashes throughout.
"""
from typing import Dict, Any, List
from .models import ConfigVersion
from .default_taxonomies import DEFAULT_TAXONOMY_DATA


def get_active_taxonomies() -> Dict[str, Any]:
    """
    Retrieve active candidate choices and taxonomy matrix.
    Falls back gracefully to DEFAULT_TAXONOMY_DATA if no active row exists yet.
    """
    active = ConfigVersion.objects.filter(
        key=ConfigVersion.Key.SKILL_TAXONOMY,
        is_active=True
    ).first()

    if active and isinstance(active.data, dict) and active.data.get("sectors"):
        return {
            "version": active.version,
            "data": active.data,
            "published_at": active.created_at.isoformat(),
            "author": active.author.email if active.author else "System Defaults",
            "notes": active.notes,
        }

    return {
        "version": 0,
        "data": DEFAULT_TAXONOMY_DATA,
        "published_at": None,
        "author": "System Baseline",
        "notes": "Baseline platform choices",
    }


def get_taxonomy_history(limit: int = 15) -> List[Dict[str, Any]]:
    """
    Retrieve historical versions of the taxonomy matrix for rollbacks or auditing.
    """
    versions = ConfigVersion.objects.filter(
        key=ConfigVersion.Key.SKILL_TAXONOMY
    ).order_by("-version")[:limit]

    history = []
    for v in versions:
        history.append({
            "version": v.version,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat(),
            "author": v.author.email if v.author else "System",
            "notes": v.notes,
            "item_counts": {
                "sectors": len(v.data.get("sectors", [])),
                "domains": len(v.data.get("domains", [])),
                "skills": len(v.data.get("skills", [])),
                "seniorities": len(v.data.get("seniorities", [])),
                "workAuths": len(v.data.get("workAuths", [])),
                "engagements": len(v.data.get("engagements", [])),
            } if isinstance(v.data, dict) else {},
        })
    return history
