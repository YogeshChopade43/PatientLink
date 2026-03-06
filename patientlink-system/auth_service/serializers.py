from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'password',
            'clinic_name',
            'created_at',
            'is_active',
            'is_staff',
            'is_superuser',
        )
        read_only_fields = ('is_active', 'is_staff', 'is_superuser')
        
    def create(self, validated_data):
        # Hash the password before saving
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(required=False, allow_blank=True, write_only=True)
    
    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')
        
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid username or password.')
            
        # Check password manually since we're not using Django's default User model
        from django.contrib.auth.hashers import check_password
        if not check_password(password, user.password):
            raise serializers.ValidationError('Invalid username or password.')
            
        attrs['user'] = user
        return attrs


class VerifyTokenSerializer(serializers.Serializer):
    token = serializers.CharField()
