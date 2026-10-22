import pytest
from apps.accounts.models import User
from apps.candidates.models import Candidate, SectorChoice, ExperienceLevel, SkillTaxonomy, CandidateSkill
from apps.ats.models import Client, Requisition, RequisitionStatus, RequisitionVisibility, Application, ApplicationStage, ApplicationSource
from apps.leads.models import Lead, LeadSource, LeadStatus
from apps.config_center.services import publish_config, get_active_config
from apps.referrals.models import Referral, ReferralType, ReferralStage, LedgerEntry, PayoutStatus


@pytest.mark.django_db
def test_base_model_soft_delete_and_uuidv7():
    skill = SkillTaxonomy.objects.create(name='Python', skill_type='tech')
    assert skill.id is not None
    assert skill.created_at is not None
    assert skill.archived_at is None

    # Test soft delete
    skill_id = skill.id
    skill.archive()
    assert skill.archived_at is not None

    # Default manager excludes archived
    assert SkillTaxonomy.objects.filter(id=skill_id).exists() is False
    # All objects manager includes archived
    assert SkillTaxonomy.all_objects.filter(id=skill_id).exists() is True

    # Restore
    skill.restore()
    assert skill.archived_at is None
    assert SkillTaxonomy.objects.filter(id=skill_id).exists() is True


@pytest.mark.django_db
def test_candidate_profile_and_skills():
    user = User.objects.create_user(
        email='dev.candidate@pepoltek.com',
        password='Password123!',
        full_name='Elena Rostova'
    )
    candidate = Candidate.objects.create(
        user=user,
        full_name='Elena Rostova',
        phone='+14155552671',
        sector=SectorChoice.TECHNOLOGY,
        domain='Fullstack & AI',
        level=ExperienceLevel.SENIOR,
        open_to_work=True,
    )
    assert candidate.user == user
    assert candidate.full_name == 'Elena Rostova'

    # Add skill
    skill = SkillTaxonomy.objects.create(name='Django', skill_type='tech')
    c_skill = CandidateSkill.objects.create(
        candidate=candidate,
        skill=skill,
        years_experience=6,
        proficiency='expert',
    )
    assert c_skill.candidate == candidate
    assert candidate.skills.count() == 1


@pytest.mark.django_db
def test_ats_client_requisition_and_application_pipeline():
    staff = User.objects.create_user(
        email='recruiter@pepoltek.com',
        password='RecruiterPassword123!',
        full_name='Sarah Recruiter'
    )
    client = Client.objects.create(
        name='Acme Healthcare Systems',
        sector='Healthcare',
        owner=staff
    )
    req = Requisition.objects.create(
        client=client,
        title='Senior Telehealth Backend Engineer',
        sector='technology',
        level='senior',
        status=RequisitionStatus.OPEN,
        visibility=RequisitionVisibility.PUBLISHED_JOB,
        owner=staff
    )
    assert req.client == client

    candidate_user = User.objects.create_user(
        email='applicant@pepoltek.com',
        password='ApplicantPassword123!',
        full_name='James Miller'
    )
    candidate = Candidate.objects.create(
        user=candidate_user,
        full_name='James Miller',
        sector=SectorChoice.TECHNOLOGY,
        level=ExperienceLevel.SENIOR
    )

    # 5-stage Application progression
    app = Application.objects.create(
        candidate=candidate,
        requisition=req,
        stage=ApplicationStage.DISCOVERY,
        source=ApplicationSource.APPLIED,
        owner=staff
    )
    assert app.stage == ApplicationStage.DISCOVERY

    # Transition to technical vetting then client interview
    app.stage = ApplicationStage.TECHNICAL_VETTING
    app.save()
    assert app.stage == ApplicationStage.TECHNICAL_VETTING

    app.stage = ApplicationStage.INTERVIEW
    app.save()
    assert app.stage == ApplicationStage.INTERVIEW


@pytest.mark.django_db
def test_lead_intake_with_calculator_snapshot():
    lead = Lead.objects.create(
        source=LeadSource.CALCULATOR,
        status=LeadStatus.NEW,
        contact_name='Alex Vance',
        work_email='alex@vance-biotech.com',
        company='Vance Biotech Corp',
        phone='+12125550199',
        sector='healthcare',
        calculator_snapshot={
            'roles': ['Senior Nurse', 'Clinical Data Lead'],
            'estimated_savings_usd': 85000,
            'velocity_days': 5
        }
    )
    assert lead.company == 'Vance Biotech Corp'
    assert lead.calculator_snapshot['estimated_savings_usd'] == 85000
    assert lead.status == LeadStatus.NEW


@pytest.mark.django_db
def test_versioned_config_center():
    admin = User.objects.create_user(
        email='admin@pepoltek.com',
        password='AdminPassword123!',
        full_name='System Admin'
    )
    # Publish version 1
    v1 = publish_config(
        key='pricing_tiers',
        data={'tech_standard_rate': 65, 'healthcare_rn_rate': 75},
        author=admin,
        notes='Initial baseline rates'
    )
    assert v1.version == 1
    assert v1.is_active is True

    # Read active
    active = get_active_config('pricing_tiers')
    assert active['version'] == 1
    assert active['data']['tech_standard_rate'] == 65

    # Publish version 2
    v2 = publish_config(
        key='pricing_tiers',
        data={'tech_standard_rate': 70, 'healthcare_rn_rate': 80},
        author=admin,
        notes='Adjusted Q4 rates'
    )
    assert v2.version == 2
    active_now = get_active_config('pricing_tiers')
    assert active_now['version'] == 2
    assert active_now['data']['tech_standard_rate'] == 70


@pytest.mark.django_db
def test_referral_attribution_and_ledger():
    referrer = User.objects.create_user(
        email='referrer@pepoltek.com',
        password='ReferrerPassword123!',
        full_name='Marcus Referrer'
    )
    candidate_user = User.objects.create_user(
        email='referred.candidate@pepoltek.com',
        password='CandidatePassword123!',
        full_name='David Kim'
    )
    candidate = Candidate.objects.create(
        user=candidate_user,
        full_name='David Kim',
        sector=SectorChoice.TECHNOLOGY,
        level=ExperienceLevel.MID
    )

    referral = Referral.objects.create(
        referrer=referrer,
        referral_type=ReferralType.CANDIDATE,
        candidate=candidate,
        stage=ReferralStage.SUBMITTED,
    )
    assert referral.referrer == referrer
    assert referral.stage == ReferralStage.SUBMITTED

    # Double-entry ledger reward entry
    ledger = LedgerEntry.objects.create(
        user=referrer,
        referral=referral,
        amount=500.00,
        currency='USD',
        milestone='placed',
        status=PayoutStatus.PENDING,
        note='Referral bonus for candidate placement'
    )
    assert ledger.amount == 500.00
    assert ledger.status == PayoutStatus.PENDING

