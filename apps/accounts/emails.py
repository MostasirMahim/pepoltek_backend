"""
Email dispatch services for accounts: staff onboarding invitations,
candidate security verification OTPs, and welcome emails.
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def send_staff_onboarding_email(
    email: str,
    full_name: str,
    role: str,
    temporary_password: str,
    login_url: str = None
) -> bool:
    """
    Dispatches a professional staff invitation and onboarding email
    with secure temporary credentials and back-office cockpit instructions.
    """
    portal_url = login_url or f"{settings.FRONTEND_URL}/staff/login"
    subject = f"Welcome to Pepoltek Staff Operations: {role} Access Granted"
    
    plain_text = f"""
Hello {full_name},

You have been granted internal staff access to the Pepoltek Platform as a {role}.

Your initial onboarding credentials:
- Corporate Email: {email}
- Temporary Password: {temporary_password}
- Access Role: {role}
- Staff Portal: {portal_url}

Next Steps:
1. Navigate to the Staff Operations Cockpit at {portal_url}
2. Sign in using your corporate email and temporary password
3. Complete two-factor authentication setup upon first login

If you have any questions or did not expect this invitation, please contact security@pepoltek.com immediately.

Best regards,
Pepoltek Platform Security & Operations
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f7f9fc; margin: 0; padding: 20px; }}
    .card {{ max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #bcd6fa; padding: 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
    .badge {{ display: inline-block; background: #e0f2fe; color: #0284c7; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }}
    .title {{ font-size: 22px; font-weight: 800; color: #0a1428; margin: 16px 0 8px 0; }}
    .desc {{ font-size: 14px; color: #475569; line-height: 1.6; }}
    .cred-box {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; margin: 20px 0; }}
    .cred-row {{ font-size: 13px; margin: 6px 0; color: #1e293b; }}
    .cred-label {{ font-weight: 600; color: #64748b; display: inline-block; width: 140px; }}
    .cred-val {{ font-family: monospace; font-weight: 700; color: #0284c7; }}
    .btn {{ display: inline-block; background: #0a1428; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 10px; font-weight: 700; font-size: 13px; margin-top: 10px; }}
    .footer {{ font-size: 11px; color: #94a3b8; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px; text-align: center; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Staff Onboarding Authorization</span>
    <h1 class="title">Welcome to Pepoltek Operations</h1>
    <p class="desc">Hello <strong>{full_name}</strong>,</p>
    <p class="desc">You have been provisioned internal back-office access to the Pepoltek Platform with role-based permissions for <strong>{role}</strong>.</p>
    
    <div class="cred-box">
      <div class="cred-row"><span class="cred-label">Corporate Email:</span> <span class="cred-val">{email}</span></div>
      <div class="cred-row"><span class="cred-label">Temporary Password:</span> <span class="cred-val">{temporary_password}</span></div>
      <div class="cred-row"><span class="cred-label">Assigned Role:</span> <span class="cred-val">{role}</span></div>
      <div class="cred-row"><span class="cred-label">Security Tier:</span> <span class="cred-val">Tier 1 Internal Staff</span></div>
    </div>

    <a href="{portal_url}" class="btn">Access Staff Operations Cockpit &rarr;</a>

    <div class="footer">
      This is an automated dispatch from the Pepoltek Platform Security Engine.<br>
      If you did not expect this invitation, please immediately contact security@pepoltek.com.
    </div>
  </div>
</body>
</html>
"""

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_text.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Staff onboarding email dispatched successfully to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch staff onboarding email to {email}: {e}")
        return False


def send_verification_otp_email(
    email: str,
    otp_code: str,
    full_name: str = "Candidate"
) -> bool:
    """
    Dispatches a candidate security verification code via email.
    """
    subject = f"Your Pepoltek Security Verification Code: {otp_code}"
    
    plain_text = f"""
Hello {full_name},

Your 6-digit Pepoltek authentication code is: {otp_code}

Please enter this verification pin in your browser to complete your account setup. This code expires in 10 minutes.

If you did not request this verification code, please ignore this email.

Best regards,
Pepoltek Security Team
"""

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f7f9fc; margin: 0; padding: 20px; }}
    .card {{ max-width: 520px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #bcd6fa; padding: 32px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); text-align: center; }}
    .badge {{ display: inline-block; background: #eff6ff; color: #0284c7; padding: 4px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; text-transform: uppercase; }}
    .title {{ font-size: 22px; font-weight: 800; color: #0a1428; margin: 16px 0 8px 0; }}
    .desc {{ font-size: 13px; color: #475569; line-height: 1.5; }}
    .otp-box {{ background: #eff6ff; border: 2px dashed #0284c7; border-radius: 12px; padding: 16px; margin: 24px auto; max-width: 260px; }}
    .otp-code {{ font-family: monospace; font-size: 32px; font-weight: 800; color: #0a1428; letter-spacing: 6px; }}
    .footer {{ font-size: 11px; color: #94a3b8; margin-top: 24px; border-top: 1px solid #e2e8f0; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">Two-Factor Security Verification</span>
    <h1 class="title">Verify Your Email Address</h1>
    <p class="desc">Hello {full_name}, enter the following 6-digit security code to verify your candidate talent profile:</p>
    
    <div class="otp-box">
      <div class="otp-code">{otp_code}</div>
    </div>

    <p class="desc">This code expires in 10 minutes. Never share this code with anyone.</p>

    <div class="footer">
      Pepoltek Limited &bull; Enterprise Talent &amp; Clinical Talent Network<br>
      If you did not initiate this request, you can safely discard this email.
    </div>
  </div>
</body>
</html>
"""

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_text.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Verification OTP email dispatched to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch OTP email to {email}: {e}")
        return False
