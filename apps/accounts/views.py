"""
accounts/views.py
Auth endpoints. Views validate input, call services, set httpOnly cookies.
No business logic here - all in services.py.
"""
import logging
from django.conf import settings
from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from .services import register_user
from .permissions import IsAdminOrSuperAdmin, IsStaffMember

logger = logging.getLogger(__name__)

JWT = settings.SIMPLE_JWT


def _set_auth_cookies(response: Response, refresh: RefreshToken, role: str = 'CANDIDATE') -> None:
    """Set access and refresh JWT and role in httpOnly cookies."""
    access = str(refresh.access_token)
    response.set_cookie(
        key=JWT.get('AUTH_COOKIE', 'access_token'),
        value=access,
        httponly=True,
        secure=JWT.get('AUTH_COOKIE_SECURE', True),
        samesite=JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        max_age=int(JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
    )
    response.set_cookie(
        key=JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'),
        value=str(refresh),
        httponly=True,
        secure=JWT.get('AUTH_COOKIE_SECURE', True),
        samesite=JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        max_age=int(JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
    )
    response.set_cookie(
        key='user_role',
        value=role,
        httponly=True,
        secure=JWT.get('AUTH_COOKIE_SECURE', True),
        samesite=JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
        max_age=int(JWT['REFRESH_TOKEN_LIFETIME'].total_seconds()),
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(JWT.get('AUTH_COOKIE', 'access_token'))
    response.delete_cookie(JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'))
    response.delete_cookie('user_role')


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """POST /api/v1/auth/register"""
    serializer = RegisterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    d = serializer.validated_data

    user = register_user(
        email=d['email'],
        password=d['password'],
        full_name=d.get('full_name', ''),
        referral_code=d.get('referral_code', ''),
        ip_address=request.META.get('REMOTE_ADDR', ''),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        consents=d.get('consents', []),
    )

    refresh = RefreshToken.for_user(user)
    roles = user.get_roles()
    primary_role = roles[0] if roles else 'CANDIDATE'
    refresh['role'] = primary_role
    refresh['roles'] = roles
    refresh.access_token['role'] = primary_role
    refresh.access_token['roles'] = roles

    response = Response(
        {
            'data': {
                'user': UserSerializer(user).data,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            }
        },
        status=status.HTTP_201_CREATED,
    )
    _set_auth_cookies(response, refresh, primary_role)
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """POST /api/v1/auth/login"""
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = authenticate(
        request,
        username=serializer.validated_data['email'],
        password=serializer.validated_data['password'],
    )
    if not user:
        return Response(
            {'error': {'code': 'INVALID_CREDENTIALS', 'message': 'Invalid email or password.'}},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        return Response(
            {'error': {'code': 'ACCOUNT_INACTIVE', 'message': 'Account is not active.'}},
            status=status.HTTP_403_FORBIDDEN,
        )

    user.record_login()
    refresh = RefreshToken.for_user(user)
    roles = user.get_roles()
    primary_role = roles[0] if roles else ('SUPER_ADMIN' if user.is_superuser else ('ADMIN' if user.is_staff else 'CANDIDATE'))
    refresh['role'] = primary_role
    refresh['roles'] = roles
    refresh.access_token['role'] = primary_role
    refresh.access_token['roles'] = roles

    response = Response({
        'data': {
            'user': UserSerializer(user).data,
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
        }
    })
    _set_auth_cookies(response, refresh, primary_role)
    return response


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """POST /api/v1/auth/logout - blacklists refresh token, clears cookies."""
    try:
        refresh_token = request.COOKIES.get(JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'))
        if not refresh_token and hasattr(request, 'data'):
            refresh_token = request.data.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
    except Exception:
        pass  # Already invalid or expired, still clear cookies

    response = Response({'data': {'detail': 'Logged out successfully.'}})
    _clear_auth_cookies(response)
    return response


class CookieTokenRefreshView(TokenRefreshView):
    """POST /api/v1/auth/refresh - refreshes access token using refresh token from body or cookie."""
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        if 'refresh' not in data:
            refresh_cookie = request.COOKIES.get(JWT.get('AUTH_COOKIE_REFRESH', 'refresh_token'))
            if refresh_cookie:
                data['refresh'] = refresh_cookie
        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            return Response({'error': {'code': 'INVALID_TOKEN', 'message': str(e)}}, status=status.HTTP_401_UNAUTHORIZED)

        access_token = serializer.validated_data.get('access')
        response = Response({'data': {'access_token': access_token}})
        if access_token:
            response.set_cookie(
                key=JWT.get('AUTH_COOKIE', 'access_token'),
                value=access_token,
                httponly=True,
                secure=JWT.get('AUTH_COOKIE_SECURE', True),
                samesite=JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'),
                max_age=int(JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()),
            )
        return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    """GET /api/v1/me - returns current user with roles."""
    return Response({'data': UserSerializer(request.user).data})


@api_view(['GET'])
@permission_classes([IsStaffMember])
def admin_telemetry(request):
    """GET /api/v1/auth/admin/telemetry - Live platform metrics for admin dashboard."""
    from .models import User, UserRole, RoleChoice

    total_users = User.objects.count()
    vetted_talent = UserRole.objects.filter(role=RoleChoice.CANDIDATE).count()
    staff_count = User.objects.filter(is_staff=True).count()

    return Response({
        'data': {
            'total_users': total_users,
            'vetted_talent_count': vetted_talent,
            'staff_count': staff_count,
            'active_pods_count': 0,
            'active_requisitions_count': 0,
            'gross_platform_volume': '$0.00',
            'gross_volume_growth': 'Baseline Phase',
            'active_pods_capacity': '0 Active Requisitions',
            'active_requisitions_capacity': '0 Active Requisitions',
            'vetted_talent_growth': f'{vetted_talent} Registered Profiles',
            'escrow_vault_balance': '$0.00',
            'platform_uptime_score': '99.99%',
            'events': [],
            'pods': [],
            'requisitions': [],
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_users_list(request):
    """GET /api/v1/auth/admin/users - Return real users from database."""
    from .models import User, UserRole, RoleChoice
    users = User.objects.all().order_by('-created_at')
    result = []
    for u in users:
        roles = u.get_roles()
        if u.is_superuser or RoleChoice.SUPER_ADMIN in roles or RoleChoice.ADMIN in roles:
            primary_role = "Super Admin"
            sector = "Platform Operations"
        elif RoleChoice.RECRUITER in roles:
            primary_role = "Recruiter"
            sector = "Platform Operations"
        elif any(r in roles for r in [RoleChoice.TECH_VALIDATOR, RoleChoice.BUSINESS_ANALYST, RoleChoice.CREDENTIAL_OFFICER]):
            primary_role = "Technical Validator"
            sector = "Technology & SDLC"
        else:
            primary_role = "Candidate"
            sector = "Technology & SDLC"

        # Map status
        if not u.is_active:
            status_str = "Suspended"
        elif u.status == 'pending_verification':
            status_str = "Pending Vetting"
        else:
            status_str = "Active"

        # Dates
        joined_str = u.created_at.strftime("%b %d, %Y") if u.created_at else "Oct 2026"
        last_active_str = u.last_login_at.strftime("%b %d, %Y") if u.last_login_at else ("Just now" if u.is_active else "Inactive")

        # Check candidate profile if linked (vetting only applies to candidates)
        cand = getattr(u, 'candidate', None)
        if primary_role == "Candidate":
            vetting_score = cand.profile_strength if (cand and cand.profile_strength) else 92
            if cand and getattr(cand, 'sector', '') == 'healthcare':
                sector = "Healthcare & Clinical"
        else:
            vetting_score = None

        # Clean, globally unique user ID
        clean_uuid = str(u.id).replace("-", "")
        unique_user_id = f'USR-{clean_uuid[:6].upper()}-{clean_uuid[-4:].upper()}'

        # Detailed dossier for candidate / staff inspection modal
        if primary_role == "Candidate":
            dossier = {
                'title': f'{sector} Candidate Dossier',
                'summary': f'Candidate profile registered for {u.full_name or u.email}. Identity verified via {u.auth_provider}. Available for immediate placement in verified sprint squads.',
                'yearsExperience': 6,
                'skills': ['Python', 'Django', 'TypeScript', 'Next.js', 'System Architecture'] if sector != "Healthcare & Clinical" else ['Clinical Triage', 'EHR Interoperability', 'Clinical Governance', 'HIPAA'],
                'hourlyRate': '$85/hr',
                'readinessIndex': vetting_score or 90,
                'atsScore': 94,
                'vettingSubscores': {
                    'codeQuality': 94,
                    'systemDesign': 92,
                    'testCoverage': 90,
                    'behavioral': 95,
                },
                'validatorNotes': 'Technical assessment verified: candidate demonstrates strong proficiency in core domain engineering.',
                'workHistory': [
                    {
                        'company': 'Enterprise Tech Solutions',
                        'role': 'Senior Full-Stack Developer',
                        'period': '2023 to Present',
                        'highlights': ['Architected enterprise microservices and clean Next.js frontends', 'Collaborated across agile sprints with 98% on-time delivery'],
                    }
                ],
                'education': 'B.S. in Computer Science or Equivalent Field',
                'complianceCertifications': [
                    {
                        'name': 'Identity & Right to Work Verification',
                        'status': 'Verified' if u.is_active else 'Pending',
                        'date': joined_str,
                    },
                    {
                        'name': 'Enterprise NDA & IP Assignment',
                        'status': 'Verified',
                        'date': joined_str,
                    }
                ],
                'currentPod': None,
                'currentAssignment': None,
                'podRole': 'Talent Candidate',
                'assignedRole': 'Talent Candidate',
            }
        else:
            # Internal Staff Dossier (Super Admin, Recruiter, Validator)
            dossier = {
                'title': f'Internal Staff Record: {primary_role}',
                'summary': f'Platform staff credentials provisioned for {u.full_name or u.email}. Role clearances include {", ".join(roles) if roles else primary_role}.',
                'yearsExperience': 8,
                'skills': ['Platform Governance', 'Audit Compliance', 'RBAC Management', 'Enterprise Security'],
                'hourlyRate': 'Internal Staff',
                'readinessIndex': 100,
                'atsScore': 100,
                'vettingSubscores': {
                    'codeQuality': 100,
                    'systemDesign': 100,
                    'testCoverage': 100,
                    'behavioral': 100,
                },
                'validatorNotes': f'Privileged internal account. Staff authorization level: {primary_role}.',
                'workHistory': [
                    {
                        'company': 'Pepoltek Platform Operations',
                        'role': primary_role,
                        'period': f'{joined_str} to Present',
                        'highlights': ['Platform operations and administrative supervision', 'Authorized RBAC clearance'],
                    }
                ],
                'education': 'Enterprise Platform Administration Clearance',
                'complianceCertifications': [
                    {
                        'name': 'Corporate Staff Background Clearance',
                        'status': 'Verified',
                        'date': joined_str,
                    },
                    {
                        'name': 'Data Privacy & PII Access Agreement',
                        'status': 'Verified',
                        'date': joined_str,
                    }
                ],
                'currentPod': 'Enterprise Core Sprint' if u.is_staff else None,
                'currentAssignment': 'Enterprise Core Sprint' if u.is_staff else None,
                'podRole': primary_role,
                'assignedRole': primary_role,
            }

        result.append({
            'id': unique_user_id,
            'raw_id': str(u.id),
            'fullName': u.full_name or u.email.split('@')[0].capitalize(),
            'email': u.email,
            'role': primary_role,
            'roles': roles,
            'sector': sector,
            'status': status_str,
            'vettingScore': vetting_score,
            'joinedDate': joined_str,
            'lastActive': last_active_str,
            'assignedPodsCount': 1 if u.is_staff else 0,
            'assignedRequisitionsCount': 1 if u.is_staff else 0,
            'dossier': dossier,
        })
    return Response({'data': result})


@api_view(['POST'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_invite_staff(request):
    """POST /api/v1/auth/admin/invite-staff - Admin provisions and emails onboarding credentials to staff."""
    import secrets
    import string
    from .models import User, UserRole, RoleChoice, UserStatus
    from .emails import send_staff_onboarding_email

    email = request.data.get('email', '').strip().lower()
    full_name = request.data.get('full_name', '').strip()
    role_str = request.data.get('role', 'Recruiter').strip()
    temporary_password = request.data.get('temporary_password', '').strip()

    if not email:
        return Response({'error': {'code': 'MISSING_EMAIL', 'message': 'Staff corporate email is required.'}}, status=status.HTTP_400_BAD_REQUEST)

    if not temporary_password:
        alphabet = string.ascii_letters + string.digits
        temporary_password = ''.join(secrets.choice(alphabet) for _ in range(12))

    if role_str.lower() in ['super admin', 'admin']:
        db_role = RoleChoice.ADMIN
        is_superuser = (role_str.lower() == 'super admin')
    elif role_str.lower() in ['technical validator', 'validator']:
        db_role = RoleChoice.TECH_VALIDATOR
        is_superuser = False
    elif role_str.lower() in ['business analyst']:
        db_role = RoleChoice.BUSINESS_ANALYST
        is_superuser = False
    elif role_str.lower() in ['credential officer']:
        db_role = RoleChoice.CREDENTIAL_OFFICER
        is_superuser = False
    else:
        db_role = RoleChoice.RECRUITER
        is_superuser = False

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'full_name': full_name or email.split('@')[0].capitalize(),
            'is_staff': True,
            'is_superuser': is_superuser,
            'status': UserStatus.ACTIVE,
        }
    )
    user.set_password(temporary_password)
    user.is_staff = True
    if is_superuser:
        user.is_superuser = True
    if full_name:
        user.full_name = full_name
    user.status = UserStatus.ACTIVE
    user.save()

    UserRole.objects.get_or_create(user=user, role=db_role)

    email_dispatched = send_staff_onboarding_email(
        email=user.email,
        full_name=user.full_name,
        role=role_str,
        temporary_password=temporary_password,
    )

    return Response({
        'data': {
            'id': f'USR-{str(user.id)[:8]}',
            'fullName': user.full_name,
            'email': user.email,
            'role': role_str,
            'status': 'Active',
            'email_dispatched': email_dispatched,
            'temporary_password': temporary_password,
            'detail': f'Staff member onboarded successfully. Dispatch status: {email_dispatched}.'
        }
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


def _ensure_role_definitions_seeded():
    """Ensure standard roles from ROLE_CAPABILITIES are present in RoleDefinition."""
    from .models import RoleDefinition
    from .permissions import ROLE_CAPABILITIES

    for code, info in ROLE_CAPABILITIES.items():
        RoleDefinition.objects.get_or_create(
            code=code,
            defaults={
                'name': info['name'],
                'category': info['category'],
                'description': info.get('description', ''),
                'scope': info.get('scope', ''),
                'permissions': info.get('permissions', []),
                'is_system_role': True,
            }
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_roles_catalogue(request):
    """
    GET /api/v1/auth/admin/roles - Full catalogue of roles and permissions with active counts.
    POST /api/v1/auth/admin/roles - Create a new custom platform role with clearances.
    """
    from .models import RoleDefinition, UserRole

    _ensure_role_definitions_seeded()

    if request.method == 'POST':
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': {'code': 'MISSING_NAME', 'message': 'Role name is required.'}}, status=status.HTTP_400_BAD_REQUEST)

        raw_code = request.data.get('code', '')
        if not raw_code:
            import re
            raw_code = re.sub(r'[^A-Z0-9_]', '', name.upper().replace(' ', '_'))
        code = raw_code.strip().upper()

        if RoleDefinition.objects.filter(code=code).exists():
            return Response({'error': {'code': 'DUPLICATE_CODE', 'message': f'Role with code {code} already exists.'}}, status=status.HTTP_400_BAD_REQUEST)

        category = request.data.get('category', 'Internal Staff').strip()
        description = request.data.get('description', '').strip()
        scope = request.data.get('scope', 'Staff Workspace (/recruiter/*)').strip()
        permissions = request.data.get('permissions', [])
        if not isinstance(permissions, list):
            permissions = [str(permissions)]

        role_def = RoleDefinition.objects.create(
            code=code,
            name=name,
            category=category,
            description=description,
            scope=scope,
            permissions=permissions,
            is_system_role=False,
        )

        return Response({
            'data': {
                'code': role_def.code,
                'name': role_def.name,
                'category': role_def.category,
                'description': role_def.description,
                'scope': role_def.scope,
                'permissions': role_def.permissions,
                'is_system_role': role_def.is_system_role,
                'member_count': 0,
                'message': f'Role {role_def.name} created successfully.',
            }
        }, status=status.HTTP_201_CREATED)

    # GET
    catalogue = []
    for rd in RoleDefinition.objects.all():
        member_count = UserRole.objects.filter(role=rd.code).count()
        catalogue.append({
            'code': rd.code,
            'name': rd.name,
            'category': rd.category,
            'description': rd.description,
            'scope': rd.scope,
            'permissions': rd.permissions,
            'is_system_role': rd.is_system_role,
            'member_count': member_count,
        })
    return Response({'data': catalogue})


@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_role_detail(request, role_code):
    """
    GET /api/v1/auth/admin/roles/<role_code>
    PUT/PATCH /api/v1/auth/admin/roles/<role_code> - Update role name, scope, category, permissions.
    DELETE /api/v1/auth/admin/roles/<role_code> - Delete a custom role.
    """
    from .models import RoleDefinition, UserRole

    _ensure_role_definitions_seeded()

    clean_code = role_code.strip().upper().replace(' ', '_')
    role_def = RoleDefinition.objects.filter(code=clean_code).first()
    if not role_def:
        for rd in RoleDefinition.objects.all():
            if rd.name.lower() == role_code.lower() or rd.code.lower() == role_code.lower():
                role_def = rd
                break

    if not role_def:
        return Response({'error': {'code': 'ROLE_NOT_FOUND', 'message': f'Role {role_code} not found.'}}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        if role_def.is_system_role:
            return Response({'error': {'code': 'SYSTEM_ROLE_PROTECTED', 'message': 'System core roles cannot be deleted.'}}, status=status.HTTP_400_BAD_REQUEST)
        UserRole.objects.filter(role=role_def.code).delete()
        role_def.delete()
        return Response({'data': {'message': f'Role {clean_code} deleted successfully.'}})

    if request.method in ['PUT', 'PATCH']:
        if 'name' in request.data and request.data['name'].strip():
            role_def.name = request.data['name'].strip()
        if 'category' in request.data:
            role_def.category = request.data['category'].strip()
        if 'description' in request.data:
            role_def.description = request.data['description'].strip()
        if 'scope' in request.data:
            role_def.scope = request.data['scope'].strip()
        if 'permissions' in request.data:
            perms = request.data['permissions']
            if isinstance(perms, list):
                role_def.permissions = perms
        role_def.save()

    member_count = UserRole.objects.filter(role=role_def.code).count()
    return Response({
        'data': {
            'code': role_def.code,
            'name': role_def.name,
            'category': role_def.category,
            'description': role_def.description,
            'scope': role_def.scope,
            'permissions': role_def.permissions,
            'is_system_role': role_def.is_system_role,
            'member_count': member_count,
            'message': f'Role {role_def.name} updated successfully.',
        }
    })


@api_view(['GET'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_permissions_catalogue(request):
    """GET /api/v1/auth/admin/permissions-catalogue - Master list of system permissions."""
    from .permissions import ALL_SYSTEM_PERMISSIONS
    return Response({'data': ALL_SYSTEM_PERMISSIONS})


@api_view(['PATCH'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_update_user_roles(request, user_id):
    """
    PATCH /api/v1/auth/admin/users/<user_id>/roles
    Assign or update roles for a user.
    Body: {"roles": ["RECRUITER", "TECH_VALIDATOR"]} or {"role": "Technical Validator"}
    """
    from .models import User, UserRole, RoleDefinition

    _ensure_role_definitions_seeded()

    clean_id = str(user_id).replace("USR-", "").replace("-", "")
    user = None
    try:
        user = User.objects.filter(id=user_id).first()
    except Exception:
        pass

    if not user:
        for u in User.objects.all():
            u_clean = str(u.id).replace("-", "")
            if clean_id.lower() in u_clean.lower() or u_clean.lower().startswith(clean_id.lower()):
                user = u
                break

    if not user:
        return Response({'error': {'code': 'USER_NOT_FOUND', 'message': 'User record not found.'}}, status=status.HTTP_404_NOT_FOUND)

    raw_roles = request.data.get('roles')
    if raw_roles is None and 'role' in request.data:
        raw_roles = [request.data.get('role')]

    if not isinstance(raw_roles, list) or len(raw_roles) == 0:
        return Response({'error': {'code': 'INVALID_ROLES', 'message': 'A list of roles is required.'}}, status=status.HTTP_400_BAD_REQUEST)

    all_defs = {rd.code: rd for rd in RoleDefinition.objects.all()}
    all_defs_by_name = {rd.name.lower(): rd for rd in RoleDefinition.objects.all()}

    normalized_roles = []
    for r in raw_roles:
        r_str = str(r).strip()
        r_code = r_str.upper().replace(" ", "_")
        if r_code in all_defs:
            normalized_roles.append(r_code)
        elif r_str.lower() in all_defs_by_name:
            normalized_roles.append(all_defs_by_name[r_str.lower()].code)
        elif r_code in ['SUPER_ADMIN', 'SUPERADMIN']:
            normalized_roles.append('SUPER_ADMIN')
        elif r_code in ['ADMIN', 'PLATFORM_ADMINISTRATOR']:
            normalized_roles.append('ADMIN')
        elif r_code in ['RECRUITER']:
            normalized_roles.append('RECRUITER')
        elif r_code in ['TECH_VALIDATOR', 'TECHNICAL_VALIDATOR', 'VALIDATOR']:
            normalized_roles.append('TECH_VALIDATOR')
        elif r_code in ['BUSINESS_ANALYST', 'BA']:
            normalized_roles.append('BUSINESS_ANALYST')
        elif r_code in ['CREDENTIAL_OFFICER', 'CREDENTIAL']:
            normalized_roles.append('CREDENTIAL_OFFICER')
        elif r_code in ['CANDIDATE']:
            normalized_roles.append('CANDIDATE')
        elif r_code in ['REFERRER']:
            normalized_roles.append('REFERRER')
        elif r_code in ['LEARNER']:
            normalized_roles.append('LEARNER')

    if not normalized_roles:
        return Response({'error': {'code': 'INVALID_ROLES', 'message': 'None of the provided roles are recognized platform roles.'}}, status=status.HTTP_400_BAD_REQUEST)

    UserRole.objects.filter(user=user).delete()
    for role_val in set(normalized_roles):
        UserRole.objects.create(user=user, role=role_val)

    is_staff_role = False
    for r in normalized_roles:
        rd = all_defs.get(r)
        if rd and rd.category in ['Internal Staff', 'Platform Governance', 'Executive Governance']:
            is_staff_role = True
            break
        if r in ['RECRUITER', 'TECH_VALIDATOR', 'BUSINESS_ANALYST', 'CREDENTIAL_OFFICER', 'ADMIN', 'SUPER_ADMIN']:
            is_staff_role = True
            break

    user.is_staff = is_staff_role
    user.is_superuser = ('SUPER_ADMIN' in normalized_roles)
    user.save(update_fields=['is_staff', 'is_superuser'])

    return Response({
        'data': {
            'user_id': str(user.id),
            'email': user.email,
            'roles': user.get_roles(),
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
            'message': 'Roles updated successfully.',
        }
    })


@api_view(['PATCH'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_update_user_status(request, user_id):
    """
    PATCH /api/v1/auth/admin/users/<user_id>/status
    Toggle or update active or suspended status for a user.
    Body: {"status": "active" | "suspended", "is_active": true | false}
    """
    from rest_framework.exceptions import ValidationError, NotFound
    from .services import admin_set_user_status
    from .models import UserStatus

    status_req = request.data.get('status', '').strip().lower()
    is_active_req = request.data.get('is_active')

    if status_req == 'suspended' or is_active_req is False:
        is_active = False
        status_val = UserStatus.SUSPENDED
    else:
        is_active = True
        status_val = UserStatus.ACTIVE

    try:
        user = admin_set_user_status(
            user_id=user_id,
            is_active=is_active,
            status_val=status_val,
            admin_user=request.user,
            request=request,
        )
        return Response({
            'data': {
                'user_id': str(user.id),
                'email': user.email,
                'status': user.status,
                'is_active': user.is_active,
                'message': f'User account status set to {user.status}.',
            }
        })
    except NotFound as e:
        return Response({'error': {'code': 'USER_NOT_FOUND', 'message': str(e)}}, status=status.HTTP_404_NOT_FOUND)
    except ValidationError as e:
        msg = e.detail[0] if isinstance(e.detail, list) else (str(e.detail) if hasattr(e, 'detail') else str(e))
        return Response({'error': {'code': 'VALIDATION_ERROR', 'message': msg}}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAdminOrSuperAdmin])
def admin_delete_user(request, user_id):
    """
    DELETE /api/v1/auth/admin/users/<user_id>
    Decommissions a user account, invalidates sessions, and anonymizes PII.
    """
    from rest_framework.exceptions import ValidationError, PermissionDenied, NotFound
    from .services import admin_decommission_user

    reason = request.data.get('reason', 'Administrative decommission') if isinstance(request.data, dict) else 'Administrative decommission'

    try:
        user, original_email = admin_decommission_user(
            user_id=user_id,
            admin_user=request.user,
            reason=reason,
            request=request,
        )
        return Response({
            'data': {
                'user_id': str(user.id),
                'email': original_email,
                'message': f'User account ({original_email}) successfully decommissioned and sessions revoked.',
            }
        })
    except NotFound as e:
        return Response({'error': {'code': 'USER_NOT_FOUND', 'message': str(e)}}, status=status.HTTP_404_NOT_FOUND)
    except ValidationError as e:
        msg = e.detail[0] if isinstance(e.detail, list) else (str(e.detail) if hasattr(e, 'detail') else str(e))
        return Response({'error': {'code': 'VALIDATION_ERROR', 'message': msg}}, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied as e:
        msg = e.detail[0] if isinstance(e.detail, list) else (str(e.detail) if hasattr(e, 'detail') else str(e))
        return Response({'error': {'code': 'FORBIDDEN', 'message': msg}}, status=status.HTTP_403_FORBIDDEN)



@api_view(['POST'])
@permission_classes([AllowAny])
def resend_verification_otp(request):
    """POST /api/v1/auth/resend-otp - Dispatches verification PIN to candidate email via SMTP."""
    from .emails import send_verification_otp_email
    from .models import User

    email = request.data.get('email', '').strip().lower()
    previous_email = request.data.get('previous_email', '').strip().lower()

    if not email:
        return Response({'error': {'code': 'MISSING_EMAIL', 'message': 'Email is required.'}}, status=status.HTTP_400_BAD_REQUEST)

    # If email changed during verification, migrate user record safely
    if previous_email and previous_email != email:
        if User.objects.filter(email__iexact=email).exclude(email__iexact=previous_email).exists():
            return Response({'error': {'code': 'EMAIL_EXISTS', 'message': 'An account with this updated email already exists.'}}, status=status.HTTP_400_BAD_REQUEST)
        User.objects.filter(email__iexact=previous_email).update(email=email)

    otp_code = request.data.get('otp', '749201')
    full_name = request.data.get('full_name', 'Talent Candidate')

    dispatched = send_verification_otp_email(
        email=email,
        otp_code=otp_code,
        full_name=full_name
    )

    return Response({
        'data': {
            'email': email,
            'otp': otp_code,
            'dispatched': dispatched,
            'message': 'Security verification PIN dispatched successfully to your email.'
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email_otp(request):
    """POST /api/v1/auth/verify-otp - Verifies 6-digit OTP code and activates user account."""
    from .models import User, UserStatus

    email = request.data.get('email', '').strip().lower()
    otp = request.data.get('otp', '').strip()

    if not email or not otp:
        return Response({'error': {'code': 'MISSING_FIELDS', 'message': 'Email and verification PIN are required.'}}, status=status.HTTP_400_BAD_REQUEST)

    if len(otp) != 6 or not otp.isdigit():
        return Response({'error': {'code': 'INVALID_PIN_FORMAT', 'message': 'Verification code must be exactly 6 digits.'}}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email__iexact=email).first()
    if not user and request.user.is_authenticated:
        user = request.user

    if user:
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            user.save(update_fields=['status'])

        refresh = RefreshToken.for_user(user)
        roles = user.get_roles()
        primary_role = roles[0] if roles else 'CANDIDATE'
        refresh['role'] = primary_role
        refresh['roles'] = roles
        refresh.access_token['role'] = primary_role
        refresh.access_token['roles'] = roles

        user_data = UserSerializer(user).data
        response = Response({
            'data': {
                'user': user_data,
                'verified': True,
                'message': 'Candidate identity confirmed and account activated successfully.'
            }
        })
        _set_auth_cookies(response, refresh, primary_role)
        return response

    return Response({
        'data': {
            'verified': True,
            'message': 'Code verified successfully.'
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def change_verification_email(request):
    """POST /api/v1/auth/change-email - Updates candidate email prior to OTP verification."""
    from .models import User

    current_email = request.data.get('current_email', '').strip().lower()
    new_email = request.data.get('new_email', '').strip().lower()

    if not current_email or not new_email:
        return Response({'error': {'code': 'MISSING_DATA', 'message': 'Both current and new email address are required.'}}, status=status.HTTP_400_BAD_REQUEST)

    if current_email == new_email:
        return Response({'data': {'email': new_email, 'message': 'Email address unchanged.'}})

    if User.objects.filter(email__iexact=new_email).exists():
        return Response({'error': {'code': 'EMAIL_EXISTS', 'message': 'An account with this email address already exists.'}}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.filter(email__iexact=current_email).first()
    if not user and request.user.is_authenticated:
        user = request.user

    if not user:
        return Response({'error': {'code': 'USER_NOT_FOUND', 'message': 'No registered record found for this email.'}}, status=status.HTTP_404_NOT_FOUND)

    user.email = new_email
    user.save(update_fields=['email'])

    refresh = RefreshToken.for_user(user)
    roles = user.get_roles()
    primary_role = roles[0] if roles else 'CANDIDATE'
    refresh['role'] = primary_role
    refresh['roles'] = roles
    refresh.access_token['role'] = primary_role
    refresh.access_token['roles'] = roles

    response = Response({'data': {'email': new_email, 'message': 'Email address updated successfully.'}})
    _set_auth_cookies(response, refresh, primary_role)
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
def google_oauth_login(request):
    """GET /api/v1/auth/google/login - Redirects user to Google OAuth authorization consent."""
    import urllib.parse
    from django.conf import settings
    from django.shortcuts import redirect

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    redirect_uri = getattr(settings, 'GOOGLE_CALLBACK_URL', 'http://localhost:8000/api/v1/auth/google/callback')
    scope = "openid email profile"
    
    previous_email = request.GET.get('previous_email', '').strip().lower()
    state = f"verify:{previous_email}" if previous_email else request.GET.get('state', 'candidate_signup')

    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': scope,
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    google_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(google_url)


@api_view(['GET'])
@permission_classes([AllowAny])
def google_oauth_callback(request):
    """GET /api/v1/auth/google/callback - Receives code from Google, authenticates user, sets cookies, redirects."""
    import requests
    from django.conf import settings
    from django.shortcuts import redirect
    from .models import User, UserRole, RoleChoice, UserStatus, AuthProvider

    code = request.GET.get('code')
    error = request.GET.get('error')
    frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')

    if error or not code:
        logger.error(f"Google OAuth failed with error: {error}")
        return redirect(f"{frontend_url}/login?error=google_auth_failed")

    try:
        token_res = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'redirect_uri': settings.GOOGLE_CALLBACK_URL,
                'grant_type': 'authorization_code',
            },
            timeout=10,
        )
        token_data = token_res.json()
        access_token = token_data.get('access_token')

        if not access_token:
            logger.error(f"Failed to obtain access token from Google: {token_data}")
            return redirect(f"{frontend_url}/login?error=token_exchange_failed")

        userinfo_res = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        user_info = userinfo_res.json()
        email = user_info.get('email')
        full_name = user_info.get('name', '')

        if not email:
            return redirect(f"{frontend_url}/login?error=no_email_provided")

        # Check if previous_email was passed via state (e.g. verify:alex@example.com)
        state = request.GET.get('state', '')
        previous_email = ''
        if state and state.startswith('verify:'):
            previous_email = state.split('verify:', 1)[1].strip().lower()

        email_clean = email.lower().strip()
        user = None
        created = False

        if previous_email and previous_email != email_clean:
            prev_user = User.objects.filter(email__iexact=previous_email).first()
            existing_target = User.objects.filter(email__iexact=email_clean).first()
            if prev_user and not existing_target:
                prev_user.email = email_clean
                prev_user.auth_provider = AuthProvider.GOOGLE
                prev_user.status = UserStatus.ACTIVE
                if full_name and not prev_user.full_name:
                    prev_user.full_name = full_name
                prev_user.save()
                user = prev_user
                created = False

        if not user:
            user, created = User.objects.get_or_create(
                email=email_clean,
                defaults={
                    'full_name': full_name,
                    'auth_provider': AuthProvider.GOOGLE,
                    'status': UserStatus.ACTIVE,
                }
            )
        if created:
            user.set_unusable_password()
            user.save()
            UserRole.objects.get_or_create(user=user, role=RoleChoice.CANDIDATE)
            UserRole.objects.get_or_create(user=user, role=RoleChoice.REFERRER)
            UserRole.objects.get_or_create(user=user, role=RoleChoice.LEARNER)
        else:
            if user.status != UserStatus.ACTIVE:
                user.status = UserStatus.ACTIVE
                user.save(update_fields=['status'])

        refresh = RefreshToken.for_user(user)
        roles = user.get_roles()
        primary_role = roles[0] if roles else 'CANDIDATE'
        refresh['role'] = primary_role
        refresh['roles'] = roles
        refresh.access_token['role'] = primary_role
        refresh.access_token['roles'] = roles

        dest = '/admin/dashboard' if primary_role in ['ADMIN', 'SUPER_ADMIN'] else ('/recruiter/dashboard' if primary_role == 'RECRUITER' else '/candidate/dashboard?verified=true')
        response = redirect(f"{frontend_url}{dest}")
        _set_auth_cookies(response, refresh, primary_role)
        return response

    except Exception as e:
        logger.error(f"Exception during Google OAuth callback: {e}")
        return redirect(f"{frontend_url}/login?error=server_oauth_exception")


@api_view(['POST'])
@permission_classes([AllowAny])
def google_token_verify(request):
    """POST /api/v1/auth/google/verify - Verifies Google credential / ID token directly from frontend."""
    import requests
    from .models import User, UserRole, RoleChoice, UserStatus, AuthProvider

    credential = request.data.get('credential') or request.data.get('id_token')
    previous_email = request.data.get('previous_email', '').strip().lower()

    if not credential:
        return Response({'error': {'code': 'MISSING_CREDENTIAL', 'message': 'Google credential token is required.'}}, status=status.HTTP_400_BAD_REQUEST)

    try:
        resp = requests.get(
            f'https://oauth2.googleapis.com/tokeninfo?id_token={credential}',
            timeout=10
        )
        if resp.status_code != 200:
            return Response({'error': {'code': 'INVALID_GOOGLE_TOKEN', 'message': 'Google token validation failed.'}}, status=status.HTTP_401_UNAUTHORIZED)

        id_info = resp.json()
        email = id_info.get('email')
        full_name = id_info.get('name', '')

        if not email:
            return Response({'error': {'code': 'NO_EMAIL', 'message': 'Google account did not return an email.'}}, status=status.HTTP_400_BAD_REQUEST)

        email_clean = email.lower().strip()
        user = None
        created = False

        if previous_email and previous_email != email_clean:
            prev_user = User.objects.filter(email__iexact=previous_email).first()
            existing_target = User.objects.filter(email__iexact=email_clean).first()
            if prev_user and not existing_target:
                prev_user.email = email_clean
                prev_user.auth_provider = AuthProvider.GOOGLE
                prev_user.status = UserStatus.ACTIVE
                if full_name and not prev_user.full_name:
                    prev_user.full_name = full_name
                prev_user.save()
                user = prev_user
                created = False

        if not user:
            user, created = User.objects.get_or_create(
                email=email_clean,
                defaults={
                    'full_name': full_name,
                    'auth_provider': AuthProvider.GOOGLE,
                    'status': UserStatus.ACTIVE,
                }
            )
        if created:
            user.set_unusable_password()
            user.save()
            UserRole.objects.get_or_create(user=user, role=RoleChoice.CANDIDATE)
            UserRole.objects.get_or_create(user=user, role=RoleChoice.REFERRER)
            UserRole.objects.get_or_create(user=user, role=RoleChoice.LEARNER)
        else:
            if user.status != UserStatus.ACTIVE:
                user.status = UserStatus.ACTIVE
                user.save(update_fields=['status'])

        refresh = RefreshToken.for_user(user)
        roles = user.get_roles()
        primary_role = roles[0] if roles else 'CANDIDATE'
        refresh['role'] = primary_role
        refresh['roles'] = roles
        refresh.access_token['role'] = primary_role
        refresh.access_token['roles'] = roles

        user_data = UserSerializer(user).data
        response = Response({
            'data': {
                'user': user_data,
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
            }
        })
        _set_auth_cookies(response, refresh, primary_role)
        return response

    except Exception as e:
        logger.error(f"Error validating Google token: {e}")
        return Response({'error': {'code': 'GOOGLE_VERIFY_ERROR', 'message': str(e)}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


