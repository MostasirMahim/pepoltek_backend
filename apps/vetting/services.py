# vetting/services.py
"""
Vetting service layer.
All DB-mutating operations live here. Views call services; services own transactions.
"""
from django.db import transaction
from django.utils import timezone

from .models import (
    AssessmentTemplate,
    ApplicationVetting,
    VettingAnswer,
    VettingScore,
)


# ---------------------------------------------------------------------------
# AssessmentTemplate services
# ---------------------------------------------------------------------------

def create_assessment_template(*, actor, validated_data: dict) -> AssessmentTemplate:
    validated_data['created_by'] = actor
    return AssessmentTemplate.objects.create(**validated_data)


def update_assessment_template(*, instance: AssessmentTemplate, validated_data: dict) -> AssessmentTemplate:
    for attr, value in validated_data.items():
        setattr(instance, attr, value)
    instance.save()
    return instance


def archive_assessment_template(*, instance: AssessmentTemplate) -> AssessmentTemplate:
    instance.archived_at = timezone.now()
    instance.is_active   = False
    instance.save(update_fields=['archived_at', 'is_active', 'updated_at'])
    return instance


# ---------------------------------------------------------------------------
# ApplicationVetting services
# ---------------------------------------------------------------------------

@transaction.atomic
def assign_vetting(
    *,
    actor,
    application,
    template: AssessmentTemplate,
    primary_validator,
    secondary_validator_ids: list,
    scheduled_start=None,
    deadline=None,
    recruiter_notes: str = '',
    pass_threshold: int = 70,
) -> ApplicationVetting:
    """Create a vetting assignment when recruiter moves application to Stage 3."""
    vetting = ApplicationVetting.objects.create(
        application        = application,
        template           = template,
        primary_validator  = primary_validator,
        assigned_by        = actor,
        scheduled_start    = scheduled_start,
        deadline           = deadline,
        recruiter_notes    = recruiter_notes,
        pass_threshold     = pass_threshold,
        status             = ApplicationVetting.Status.PENDING,
    )
    if secondary_validator_ids:
        vetting.secondary_validators.set(secondary_validator_ids)

    # Immediately advance application stage to Stage 3: Technical Vetting
    if application.stage in ['discovery', 'market_mapping']:
        from apps.ats.models import ApplicationStage, ApplicationEvent
        from_stage = application.stage
        application.stage = ApplicationStage.TECHNICAL_VETTING
        application.sub_stage = 'Assessment Dispatched'
        application.save(update_fields=['stage', 'sub_stage', 'updated_at'])
        ApplicationEvent.objects.create(
            application=application,
            from_stage=from_stage,
            to_stage=ApplicationStage.TECHNICAL_VETTING,
            sub_stage='Assessment Dispatched',
            actor=actor,
            note=f"Technical vetting assessment '{template.title}' dispatched. Target Due Date: {deadline.strftime('%Y-%m-%d') if deadline else 'Pending'}."
        )
    return vetting


@transaction.atomic
def update_vetting_status(
    *,
    actor,
    vetting: ApplicationVetting,
    new_status: str,
    notes: str = '',
) -> ApplicationVetting:
    vetting.status = new_status
    if new_status == ApplicationVetting.Status.IN_PROGRESS and not vetting.started_at:
        vetting.started_at = timezone.now()
    if new_status == ApplicationVetting.Status.SUBMITTED:
        vetting.completed_at = timezone.now()
    if notes:
        vetting.decision_notes = notes
    vetting.save()
    return vetting


# ---------------------------------------------------------------------------
# VettingAnswer services
# ---------------------------------------------------------------------------

@transaction.atomic
def submit_vetting_answer(
    *,
    actor,
    vetting: ApplicationVetting,
    criterion_scores: list,
    notes: str = '',
    attachments: list = None,
    candidate_submission_url: str = '',
    candidate_notes: str = '',
    is_final_submission: bool = False,
) -> VettingAnswer:
    subtotal = sum(item.get('awarded_points', 0) for item in criterion_scores)
    answer = VettingAnswer.objects.create(
        vetting                  = vetting,
        submitted_by             = actor,
        criterion_scores         = criterion_scores,
        notes                    = notes,
        attachments              = attachments or [],
        candidate_submission_url = candidate_submission_url,
        candidate_notes          = candidate_notes,
        subtotal_score           = subtotal,
        is_final_submission      = is_final_submission,
    )
    if is_final_submission:
        vetting.status = ApplicationVetting.Status.SUBMITTED
        vetting.completed_at = timezone.now()
        vetting.save(update_fields=['status', 'completed_at', 'updated_at'])
    return answer


# ---------------------------------------------------------------------------
# VettingScore services
# ---------------------------------------------------------------------------

@transaction.atomic
def submit_final_score(
    *,
    actor,
    vetting: ApplicationVetting,
    score: int,
    verdict: str,
    feedback: str = '',
) -> VettingScore:
    """
    Only the primary validator may call this.
    Automatically updates ApplicationVetting.final_score and status.
    """
    vetting_score, _ = VettingScore.objects.update_or_create(
        vetting=vetting,
        defaults={
            'scored_by': actor,
            'score': score,
            'verdict': verdict,
            'feedback': feedback,
        }
    )
    vetting.final_score = score
    vetting.status = (
        ApplicationVetting.Status.PASSED
        if score >= vetting.pass_threshold
        else ApplicationVetting.Status.FAILED
    )
    if feedback:
        vetting.decision_notes = feedback
    vetting.save(update_fields=['final_score', 'status', 'decision_notes', 'updated_at'])
    return vetting_score

