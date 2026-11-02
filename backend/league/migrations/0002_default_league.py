from django.db import migrations


def create_default_league(apps, schema_editor):
    League = apps.get_model("league", "League")
    if not League.objects.exists():
        League.objects.create(
            name="Liga eFootball",
            status="REGISTRATION",
            is_active=True,
        )


def remove_default_league(apps, schema_editor):
    League = apps.get_model("league", "League")
    League.objects.filter(name="Liga eFootball").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("league", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_league, remove_default_league),
    ]
