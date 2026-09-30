# Generated manually for Cognito integration (Phase 2)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="cognito_sub",
            field=models.CharField(
                blank=True,
                help_text="Amazon Cognito user `sub` claim",
                max_length=128,
                null=True,
                unique=True,
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["cognito_sub"], name="users_user_cognito_a1b2c3_idx"),
        ),
    ]
