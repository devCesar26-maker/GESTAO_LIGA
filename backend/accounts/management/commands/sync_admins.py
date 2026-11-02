"""Promote every existing account listed in ``ADMIN_EMAILS``.

This is intentionally declarative so production does not depend on opening an
interactive shell. It never creates accounts: the person must already be
registered (or be created with ``createsuperuser``). Emails that do not exist
only produce a warning, so a deploy does not fail while the account is pending.
"""
import os

from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Promove contas existentes listadas em ADMIN_EMAILS (separadas por vírgula)."

    def handle(self, *args, **options):
        raw = os.getenv("ADMIN_EMAILS", "")
        emails = sorted({item.strip().lower() for item in raw.split(",") if item.strip()})
        if not emails:
            self.stdout.write("ADMIN_EMAILS não definido; nenhum administrador alterado.")
            return

        users = {
            user.email: user
            for user in User.objects.filter(email__in=emails)
        }
        promoted = [email for email in emails if email in users and not users[email].is_staff]
        if promoted:
            User.objects.filter(email__in=promoted).update(is_staff=True)
            self.stdout.write(
                self.style.SUCCESS(
                    "Administradores promovidos: " + ", ".join(promoted)
                )
            )
        else:
            self.stdout.write("Nenhum administrador novo para promover.")

        missing = [email for email in emails if email not in users]
        if missing:
            self.stderr.write(
                self.style.WARNING(
                    "Contas não encontradas (nada foi criado): "
                    + ", ".join(missing)
                    + ". Cadastre-se primeiro e reinicie o serviço, ou use "
                    "'python backend/manage.py set_admin <email>'."
                )
            )
