from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_user_coffee_cups_user_loyalty_points_user_qr_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_phone_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="phone_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
