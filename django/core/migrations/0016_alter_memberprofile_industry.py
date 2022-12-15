# Generated by Django 3.2.15 on 2022-10-03 19:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_alter_institution_acronym"),
    ]

    operations = [
        migrations.AlterField(
            model_name="memberprofile",
            name="industry",
            field=models.CharField(
                blank=True,
                choices=[
                    ("university", "College/University"),
                    ("educator", "K-12 Educator"),
                    ("government", "Government"),
                    ("private", "Private"),
                    ("nonprofit", "Non-Profit"),
                    ("student", "Student"),
                    ("other", "Other"),
                ],
                max_length=255,
            ),
        ),
    ]
