from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class User(AbstractUser):
    """
    Custom User model for clinic receptionists
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    clinic_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    twofa_enabled = models.BooleanField(default=False)
    twofa_secret = models.CharField(max_length=64, blank=True, default='')
    twofa_recovery_codes = models.TextField(default='[]')
    
    # Remove username_requried and make username optional for our use
    # but keep it for backwards compatibility
    
    class Meta:
        db_table = 'users'
