"""Promote or revoke the league administrator flag for an existing account.

The API treats ``is_staff`` as "admin of the league"; ``is_superuser`` only
grants full access to Django's own admin at ``/django-admin/``.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Promove (ou rebaixa) uma conta existente a administrador da liga."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email da conta que já existe.")
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="Remove is_staff e is_superuser (revoga o acesso administrativo).",
        )
        parser.add_argument(
            "--superuser",
            action="store_true",
            help="Também concede is_superuser (acesso completo ao /django-admin/).",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise CommandError(
                f"Nenhuma conta com o email {email}. Crie a conta primeiro "
                "(cadastro no site ou: python backend/manage.py createsuperuser "
                f"--email {email})."
            )

        fields = []
        if options["revoke"]:
            if user.is_staff:
                user.is_staff = False
                fields.append("is_staff")
            if user.is_superuser:
                user.is_superuser = False
                fields.append("is_superuser")
            outcome = "teve o acesso administrativo revogado"
        else:
            if not user.is_staff:
                user.is_staff = True
                fields.append("is_staff")
            if options["superuser"] and not user.is_superuser:
                user.is_superuser = True
                fields.append("is_superuser")
            outcome = "agora é administrador da liga"

        if fields:
            user.save(update_fields=fields)
            self.stdout.write(
                self.style.SUCCESS(f"{email} {outcome} ({', '.join(fields)}).")
            )
        else:
            self.stdout.write(f"{email} já está no estado desejado; nada a alterar.")
