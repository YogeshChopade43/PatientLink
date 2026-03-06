from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from django.contrib.auth.hashers import check_password, make_password
import os
import json
import secrets
import requests
from django.conf import settings
from django.db import connection
from .models import User
from .serializers import UserSerializer, LoginSerializer


def _ensure_admin_account():
    """Ensure only the built-in admin account is superuser/staff and uses admin/admin."""
    admin_user, _ = User.objects.get_or_create(
        username='admin',
        defaults={
            'password': make_password('admin'),
            'is_superuser': True,
            'is_staff': True,
            'is_active': True,
            'clinic_name': '',
        },
    )
    changed_fields = []
    if not check_password('admin', admin_user.password):
        admin_user.password = make_password('admin')
        changed_fields.append('password')
    if not admin_user.is_superuser:
        admin_user.is_superuser = True
        changed_fields.append('is_superuser')
    if not admin_user.is_staff:
        admin_user.is_staff = True
        changed_fields.append('is_staff')
    if not admin_user.is_active:
        admin_user.is_active = True
        changed_fields.append('is_active')
    if changed_fields:
        admin_user.save(update_fields=changed_fields)

    User.objects.exclude(id=admin_user.id).filter(is_superuser=True).update(
        is_superuser=False,
        is_staff=False,
    )
    return admin_user


def _active_superuser_count():
    return User.objects.filter(is_superuser=True, is_active=True).count()


def _enforce_superuser_policy(user):
    """
    Only `admin` can be superuser/staff, and it must stay superuser/staff/active.
    """
    if user.username == 'admin':
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
    else:
        user.is_superuser = False
        user.is_staff = False


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class LoginRateThrottle(UserRateThrottle):
    scope = 'login'


def _captcha_required() -> bool:
    return os.environ.get("ENABLE_CAPTCHA", "false").lower() == "true"


def _captcha_ok(request) -> bool:
    captcha_token = request.headers.get("X-CAPTCHA-TOKEN", "") or request.data.get("captcha_token", "")
    if not captcha_token:
        return False

    provider = os.environ.get("CAPTCHA_PROVIDER", "recaptcha").lower()
    remoteip = request.META.get("REMOTE_ADDR", "")
    timeout = 8

    try:
        if provider == "hcaptcha":
            secret = os.environ.get("HCAPTCHA_SECRET_KEY", "")
            if not secret:
                return False
            resp = requests.post(
                "https://hcaptcha.com/siteverify",
                data={"secret": secret, "response": captcha_token, "remoteip": remoteip},
                timeout=timeout,
            ).json()
            return bool(resp.get("success"))
        else:
            secret = os.environ.get("RECAPTCHA_SECRET_KEY", "")
            if not secret:
                return False
            resp = requests.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={"secret": secret, "response": captcha_token, "remoteip": remoteip},
                timeout=timeout,
            ).json()
            return bool(resp.get("success"))
    except Exception:
        return False


def _admin_2fa_required() -> bool:
    return os.environ.get("ENABLE_ADMIN_2FA", "false").lower() == "true"


def _verify_admin_otp(otp_value: str, secret: str) -> bool:
    if not secret:
        return False
    try:
        import pyotp
        return pyotp.TOTP(secret).verify(otp_value, valid_window=1)
    except Exception:
        return False


def _generate_recovery_codes():
    return [secrets.token_hex(4) for _ in range(8)]


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def signup(request):
    _ensure_admin_account()
    if request.data.get('username') == 'admin':
        return Response({'error': 'Username "admin" is reserved.'}, status=status.HTTP_400_BAD_REQUEST)
    if _captcha_required() and not _captcha_ok(request):
        return Response({'error': 'Captcha verification required'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        _enforce_superuser_policy(user)
        user.save(update_fields=['is_superuser', 'is_staff'])
        tokens = get_tokens_for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([LoginRateThrottle])
def login(request):
    _ensure_admin_account()
    if _captcha_required() and not _captcha_ok(request):
        return Response({'error': 'Captcha verification required'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        otp_value = serializer.validated_data.get('otp', '')

        if _admin_2fa_required() and user.username == 'admin' and user.twofa_enabled:
            if not otp_value:
                return Response({'error': 'OTP or recovery code is required for admin login.'}, status=status.HTTP_400_BAD_REQUEST)
            otp_ok = _verify_admin_otp(otp_value, user.twofa_secret)
            if not otp_ok:
                recovery_codes = json.loads(user.twofa_recovery_codes or "[]")
                if otp_value in recovery_codes:
                    recovery_codes.remove(otp_value)
                    user.twofa_recovery_codes = json.dumps(recovery_codes)
                    user.save(update_fields=['twofa_recovery_codes'])
                    otp_ok = True
            if not otp_ok:
                return Response({'error': 'Invalid OTP or recovery code.'}, status=status.HTTP_400_BAD_REQUEST)

        tokens = get_tokens_for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    serializer = TokenRefreshSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.validated_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token_value = request.data.get('refresh')
    if not refresh_token_value:
        return Response({'error': 'refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        token = RefreshToken(refresh_token_value)
        token.blacklist()
    except Exception:
        # Idempotent logout: if token is already rotated/blacklisted/expired, treat as logged out.
        pass
    return Response({'success': True}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_2fa_setup(request):
    user = request.user
    if user.username != 'admin':
        return Response({'error': 'Only admin account can configure 2FA.'}, status=status.HTTP_403_FORBIDDEN)
    import pyotp
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.username, issuer_name='PatientLink')
    recovery_codes = _generate_recovery_codes()
    user.twofa_secret = secret
    user.twofa_enabled = False
    user.twofa_recovery_codes = json.dumps(recovery_codes)
    user.save(update_fields=['twofa_secret', 'twofa_enabled', 'twofa_recovery_codes'])
    return Response({
        'otpauth_uri': uri,
        'secret': secret,
        'recovery_codes': recovery_codes,
        'enabled': False,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_2fa_enable(request):
    user = request.user
    if user.username != 'admin':
        return Response({'error': 'Only admin account can configure 2FA.'}, status=status.HTTP_403_FORBIDDEN)
    otp = request.data.get('otp', '')
    if not user.twofa_secret:
        return Response({'error': 'Run setup first.'}, status=status.HTTP_400_BAD_REQUEST)
    if not _verify_admin_otp(otp, user.twofa_secret):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
    user.twofa_enabled = True
    user.save(update_fields=['twofa_enabled'])
    return Response({'enabled': True}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_2fa_disable(request):
    user = request.user
    if user.username != 'admin':
        return Response({'error': 'Only admin account can configure 2FA.'}, status=status.HTTP_403_FORBIDDEN)
    otp = request.data.get('otp', '')
    if user.twofa_enabled and not _verify_admin_otp(otp, user.twofa_secret):
        return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)
    user.twofa_enabled = False
    user.twofa_secret = ''
    user.twofa_recovery_codes = '[]'
    user.save(update_fields=['twofa_enabled', 'twofa_secret', 'twofa_recovery_codes'])
    return Response({'enabled': False}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_token(request):
    from rest_framework_simplejwt.tokens import AccessToken

    auth_header = request.META.get('HTTP_AUTHORIZATION', '')

    if not auth_header:
        return Response({'valid': False, 'error': 'No authorization header'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]  # Remove 'Bearer ' prefix
    else:
        token = auth_header

    try:
        # Manually validate and decode the token
        access_token = AccessToken(token)
        user_id = access_token.get('user_id')

        try:
            user = User.objects.get(id=user_id)
            return Response({
                'valid': True,
                'user': UserSerializer(user).data
            })
        except User.DoesNotExist:
            return Response({'valid': False, 'error': 'User not found'}, status=status.HTTP_401_UNAUTHORIZED)
    except Exception as e:
        return Response({'valid': False, 'error': str(e)}, status=status.HTTP_401_UNAUTHORIZED)


@api_view(['GET'])
@permission_classes([AllowAny])
def system_readiness(request):
    """
    Readiness check for auth service dependencies and security configuration.
    Returns HTTP 503 until required checks pass.
    """
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False

    _ensure_admin_account()
    admin_user = User.objects.filter(username='admin').first()
    admin_policy_ok = bool(
        admin_user and admin_user.is_active and admin_user.is_staff and admin_user.is_superuser
    )

    token_blacklist_enabled = 'rest_framework_simplejwt.token_blacklist' in settings.INSTALLED_APPS

    captcha_enabled = _captcha_required()
    captcha_provider = os.environ.get("CAPTCHA_PROVIDER", "recaptcha").lower()
    if captcha_provider == "hcaptcha":
        captcha_secret_ok = bool(os.environ.get("HCAPTCHA_SECRET_KEY", ""))
    else:
        captcha_secret_ok = bool(os.environ.get("RECAPTCHA_SECRET_KEY", ""))
    captcha_ready = (not captcha_enabled) or captcha_secret_ok

    admin_2fa_enabled = _admin_2fa_required()
    try:
        import pyotp  # noqa: F401
        pyotp_installed = True
    except Exception:
        pyotp_installed = False
    admin_2fa_ready = (not admin_2fa_enabled) or pyotp_installed

    checks = {
        'database': db_ok,
        'admin_policy': admin_policy_ok,
        'token_blacklist_enabled': token_blacklist_enabled,
        'captcha_ready': captcha_ready,
        'admin_2fa_ready': admin_2fa_ready,
        'sentry_configured': bool(os.environ.get("SENTRY_DSN", "")),
    }
    is_ready = all(v for k, v in checks.items() if k != 'sentry_configured')
    response_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response({
        'ready': is_ready,
        'service': 'Auth Service',
        'checks': checks,
    }, status=response_status)


# Admin endpoints for user management
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def user_list(request):
    """List all users or create a new user"""
    _ensure_admin_account()
    if request.method == 'GET':
        users = User.objects.all().order_by('-created_at')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        if request.data.get('username') == 'admin':
            return Response(
                {'error': 'The admin account already exists and cannot be recreated.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Make a mutable copy of the data
        data = request.data.copy()
        data.pop('is_superuser', None)
        data.pop('is_staff', None)
        data.pop('is_active', None)
        
        # Hash password if provided
        if 'password' in data and data['password']:
            data['password'] = make_password(data['password'])
        
        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            _enforce_superuser_policy(user)
            user.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def user_detail(request, user_id):
    """Get, update, or delete a specific user"""
    _ensure_admin_account()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        # Make a mutable copy of the data
        data = request.data.copy()
        data.pop('is_superuser', None)
        data.pop('is_staff', None)
        data.pop('is_active', None)
        
        # Hash password if provided
        if 'password' in data and data['password']:
            data['password'] = make_password(data['password'])
        
        if user.username == 'admin' and 'username' in data and data['username'] != 'admin':
            return Response(
                {'error': 'The admin superuser username cannot be changed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserSerializer(user, data=data, partial=True)
        if serializer.is_valid():
            updated_user = serializer.save()
            _enforce_superuser_policy(updated_user)
            updated_user.save()
            return Response(UserSerializer(updated_user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        if user.username == 'admin':
            return Response(
                {'error': 'The admin superuser account cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if request.user.id == user.id:
            return Response(
                {'error': 'You cannot delete your own account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if user.is_superuser and user.is_active and _active_superuser_count() <= 1:
            return Response(
                {'error': 'Cannot delete the last active superuser account.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
