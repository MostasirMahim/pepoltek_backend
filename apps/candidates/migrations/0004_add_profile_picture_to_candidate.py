# Generated migration to add profile_picture field to Candidate model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('candidates', '0003_candidate_embedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='candidate',
            name='profile_picture',
            field=models.CharField(blank=True, max_length=500, null=True, help_text='S3 object key for profile picture'),
        ),
    ]
