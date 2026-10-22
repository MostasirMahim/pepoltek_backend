"""
config_center/services.py
Read/write versioned configuration. Services layer - not views.
"""
import logging
from django.db import transaction
from .models import ConfigVersion

logger = logging.getLogger(__name__)


def get_active_config(key: str) -> dict:
    """
    Returns the data dict of the active config version for a key.
    Returns empty dict if no active version exists (ships with sensible defaults).
    """
    try:
        version = ConfigVersion.objects.get(key=key, is_active=True)
        return {'version': version.version, 'data': version.data}
    except ConfigVersion.DoesNotExist:
        logger.warning('No active config version for key: %s', key)
        return {'version': 0, 'data': {}}


@transaction.atomic
def publish_config(key: str, data: dict, author, notes: str = '') -> ConfigVersion:
    """
    Deactivate current active version and publish a new one.
    Old versions are never deleted - full history preserved.
    """
    # Deactivate current
    ConfigVersion.objects.filter(key=key, is_active=True).update(is_active=False)

    # Determine next version number
    last = ConfigVersion.objects.filter(key=key).order_by('-version').first()
    next_version = (last.version + 1) if last else 1

    new_version = ConfigVersion.objects.create(
        key=key,
        version=next_version,
        data=data,
        notes=notes,
        is_active=True,
        author=author,
    )
    logger.info('Config published: key=%s version=%s by=%s', key, next_version, author)
    return new_version


@transaction.atomic
def rollback_config(key: str, target_version: int, author) -> ConfigVersion:
    """
    Re-activates a historical config version as the current active version.
    Does NOT delete any rows. Creates a new version entry pointing to old data.
    """
    target = ConfigVersion.objects.get(key=key, version=target_version)
    return publish_config(
        key=key,
        data=target.data,
        author=author,
        notes=f'Rollback to v{target_version}',
    )


def update_taxonomies(taxonomy_data: dict, author, notes: str = '') -> ConfigVersion:
    """
    Publish a new version of the candidate choice and taxonomy matrix.
    Validates required keys: sectors, domains, skills, seniorities, workAuths, engagements.
    """
    required_keys = ['sectors', 'domains', 'skills', 'seniorities', 'workAuths', 'engagements']
    for k in required_keys:
        if k not in taxonomy_data or not isinstance(taxonomy_data[k], list):
            raise ValueError(f"Taxonomy data must include a list for '{k}'.")

    return publish_config(
        key=ConfigVersion.Key.SKILL_TAXONOMY,
        data=taxonomy_data,
        author=author,
        notes=notes or "Updated taxonomy choices from Admin Console",
    )



def calculate_estimate(inputs: dict) -> dict:
    """
    Evaluate the hiring velocity calculator given user inputs.
    Returns: { legacy_days, sprint_days, hours_reclaimed, estimate_range, ruleset_version, is_draft }
    """
    config = get_active_config(ConfigVersion.Key.HIRING_CALCULATOR)
    data = config.get('data', {})
    version = config.get('version', 0)
    is_draft = data.get('is_draft', True)

    if not data or is_draft:
        # Return placeholder until business provides the formula
        return {
            'legacy_days': '45-90',
            'sprint_days': '2-7',
            'hours_reclaimed': 80,
            'estimate_range': {'min': 0, 'max': 0},
            'ruleset_version': version,
            'is_draft': True,
            'disclaimer': 'This is a preliminary estimate. Final formula pending.',
        }

    # TODO: Implement actual formula from config data when B1 is resolved
    return {
        'legacy_days': data.get('legacy_days', 60),
        'sprint_days': data.get('sprint_days', 5),
        'hours_reclaimed': data.get('hours_reclaimed', 80),
        'estimate_range': data.get('estimate_range', {}),
        'ruleset_version': version,
        'is_draft': False,
    }
