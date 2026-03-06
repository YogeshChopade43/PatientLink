from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password, make_password
from .models import User
from .serializers import UserSerializer, LoginSerializer


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


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


# Admin endpoints for user management
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def user_list(request):
    """List all users or create a new user"""
    if request.method == 'GET':
        users = User.objects.all().order_by('-created_at')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
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
