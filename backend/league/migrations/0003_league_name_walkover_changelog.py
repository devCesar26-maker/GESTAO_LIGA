from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def fill_league_names(apps, schema_editor):
    """Existing leagues keep their name; only blank rows fall back to the default."""
    League = apps.get_model("league", "League")
    League.objects.filter(name="").update(name="Liga eFootball")


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("league", "0002_default_league"),
    ]

    operations = [
        migrations.AlterField(
            model_name="league",
            name="name",
            field=models.CharField(
                default="Liga eFootball", max_length=100, verbose_name="nome"
            ),
        ),
        migrations.RunPython(fill_league_names, migrations.RunPython.noop),
        migrations.AddField(
            model_name="match",
            name="is_walkover",
            field=models.BooleanField(default=False, verbose_name="vitória por W.O."),
        ),
        migrations.AlterField(
            model_name="matchresultlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("RESULT_REPORTED", "Resultado lançado"),
                    ("RESULT_CORRECTED", "Resultado corrigido"),
                    ("RESULT_CONFIRMED", "Resultado confirmado"),
                    ("RESULT_CONTESTED", "Resultado contestado"),
                    ("RESULT_WALKOVER", "Vitória por W.O."),
                    ("KICKOFF_CHANGED", "Data alterada"),
                    ("FIXTURES_GENERATED", "Confrontos gerados"),
                    ("FIXTURES_REGENERATED", "Confrontos regerados"),
                ],
                max_length=30,
                verbose_name="ação",
            ),
        ),
        migrations.CreateModel(
            name="LeagueChangeLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[("NAME_CHANGED", "Nome alterado")],
                        max_length=30,
                        verbose_name="ação",
                    ),
                ),
                ("previous", models.JSONField(blank=True, default=dict, verbose_name="valores anteriores")),
                ("new", models.JSONField(blank=True, default=dict, verbose_name="novos valores")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="quando")),
                (
                    "league",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="change_logs",
                        to="league.league",
                        verbose_name="liga",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="league_logs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuário",
                    ),
                ),
            ],
            options={
                "verbose_name": "registro de configuração da liga",
                "verbose_name_plural": "registros de configuração da liga",
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["league", "-created_at"], name="league_leag_league__02a910_idx")],
            },
        ),
    ]
