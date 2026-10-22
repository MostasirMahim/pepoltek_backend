import pytest
from rest_framework.test import APIClient
from apps.accounts.models import User, UserRole


@pytest.mark.django_db
def test_user_registration_and_jwt_cookies():
    client = APIClient()
    payload = {
        'email': 'candidate.test@example.com',
        'password': 'SecurePassword123!',
        'full_name': 'Test Candidate',
        'consents': [
            {'policy_type': 'terms_of_service', 'policy_version': '1.0', 'agreed': True},
            {'policy_type': 'privacy_policy', 'policy_version': '1.0', 'agreed': True},
        ]
    }
    response = client.post('/api/v1/auth/register', payload, format='json')
    assert response.status_code == 201
    data = response.json().get('data', {})
    assert data['email'] == 'candidate.test@example.com'
    assert 'referral_code' in data
    assert len(data['referral_code']) > 0

    # Verify httpOnly JWT cookies are set
    cookies = response.cookies
    assert 'access_token' in cookies
    assert cookies['access_token']['httponly'] is True
    assert 'refresh_token' in cookies
    assert cookies['refresh_token']['httponly'] is True

    # Verify user exists in database with Argon2 password hash
    user = User.objects.get(email='candidate.test@example.com')
    assert user.check_password('SecurePassword123!') is True
    assert user.has_role('CANDIDATE') is True
    assert user.has_role('REFERRER') is True


@pytest.mark.django_db
def test_user_login_success_and_failure():
    client = APIClient()
    user = User.objects.create_user(
        email='login.test@example.com',
        password='ValidPassword123!',
        full_name='Login Tester',
    )
    UserRole.objects.create(user=user, role='RECRUITER')

    # Test invalid password
    bad_res = client.post('/api/v1/auth/login', {'email': user.email, 'password': 'WrongPassword!'}, format='json')
    assert bad_res.status_code == 401

    # Test valid password
    good_res = client.post('/api/v1/auth/login', {'email': user.email, 'password': 'ValidPassword123!'}, format='json')
    assert good_res.status_code == 200
    assert 'access_token' in good_res.cookies
    data = good_res.json().get('data', {})
    assert 'RECRUITER' in data['roles']


@pytest.mark.django_db
def test_auth_me_endpoint():
    client = APIClient()
    user = User.objects.create_user(
        email='me.test@example.com',
        password='ValidPassword123!',
        full_name='Me Tester',
    )
    client.force_authenticate(user=user)
    response = client.get('/api/v1/auth/me')
    assert response.status_code == 200
    assert response.json()['data']['email'] == user.email
