# Generated manually for 2FA support
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_service', '0004_user_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='twofa_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='twofa_secret',
            field=models.CharField(blank=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='user',
            name='twofa_recovery_codes',
            field=models.TextField(default='[]'),
        ),
    ]
