# Generated migration to add profile_picture field to User model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_roledefinition_alter_userrole_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='profile_picture',
            field=models.CharField(blank=True, max_length=500, null=True, help_text='S3 object key for profile picture'),
        ),
    ]
