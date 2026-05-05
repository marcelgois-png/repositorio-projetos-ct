import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.settings import DEFAULT_MYSQL_VALUES, DEFAULT_SECRET_KEY, LOCAL_ALLOWED_HOSTS, LOCAL_CSRF_ORIGINS


class Command(BaseCommand):
    help = "Verifica configuracoes essenciais antes do deploy em producao."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Retorna erro quando houver qualquer bloqueio de producao.",
        )

    def handle(self, *args, **options):
        checks = self.build_checks()
        failures = [check for check in checks if not check["ok"]]

        self.stdout.write("Verificacao de prontidao para producao")
        for check in checks:
            marker = "OK" if check["ok"] else "PENDENTE"
            style = self.style.SUCCESS if check["ok"] else self.style.ERROR
            self.stdout.write(style(f"[{marker}] {check['label']}"))
            if not check["ok"]:
                self.stdout.write(f"        {check['hint']}")

        if failures:
            summary = f"{len(failures)} pendencia(s) encontrada(s)."
            if options["strict"]:
                raise CommandError(summary)
            self.stdout.write(self.style.WARNING(summary))
            return

        self.stdout.write(self.style.SUCCESS("Ambiente pronto para validacao de producao."))

    def build_checks(self):
        return [
            self.check_debug_disabled(),
            self.check_secret_key(),
            self.check_allowed_hosts(),
            self.check_csrf_origins(),
            self.check_sqlite_disabled(),
            self.check_mysql_credentials(),
            self.check_ssl_settings(),
            self.check_email_backend(),
            self.check_static_media_paths(),
        ]

    def result(self, ok, label, hint):
        return {"ok": ok, "label": label, "hint": hint}

    def check_debug_disabled(self):
        return self.result(
            not settings.DEBUG,
            "DJANGO_DEBUG desativado",
            "Defina DJANGO_DEBUG=0 no .env de producao.",
        )

    def check_secret_key(self):
        secret_key = settings.SECRET_KEY or ""
        unique_chars = len(set(secret_key))
        ok = secret_key != DEFAULT_SECRET_KEY and len(secret_key) >= 50 and unique_chars >= 5 and not secret_key.startswith("django-insecure-")
        return self.result(
            ok,
            "DJANGO_SECRET_KEY forte",
            "Use uma chave aleatoria longa, com pelo menos 50 caracteres e boa variedade.",
        )

    def check_allowed_hosts(self):
        hosts = set(settings.ALLOWED_HOSTS)
        ok = bool(hosts) and not hosts.issubset(LOCAL_ALLOWED_HOSTS)
        return self.result(
            ok,
            "DJANGO_ALLOWED_HOSTS aponta para dominio real",
            "Informe o dominio real, por exemplo projetos.ct.ufpb.br.",
        )

    def check_csrf_origins(self):
        origins = set(settings.CSRF_TRUSTED_ORIGINS)
        ok = bool(origins) and not origins.issubset(LOCAL_CSRF_ORIGINS) and all(origin.startswith("https://") for origin in origins)
        return self.result(
            ok,
            "DJANGO_CSRF_TRUSTED_ORIGINS usa HTTPS real",
            "Informe as origens HTTPS reais, por exemplo https://projetos.ct.ufpb.br.",
        )

    def check_sqlite_disabled(self):
        using_sqlite = settings.DATABASES["default"]["ENGINE"].endswith("sqlite3")
        return self.result(
            not using_sqlite,
            "SQLite desativado",
            "Use MySQL em producao e mantenha DJANGO_USE_SQLITE desligado.",
        )

    def check_mysql_credentials(self):
        engine = settings.DATABASES["default"]["ENGINE"]
        if engine.endswith("sqlite3"):
            ok = False
        else:
            ok = True
            for env_name, default_value in DEFAULT_MYSQL_VALUES.items():
                value = os.getenv(env_name, "").strip()
                if not value or value == default_value:
                    ok = False
                    break
        return self.result(
            ok,
            "Credenciais MySQL nao usam padroes de desenvolvimento",
            "Troque MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD e MYSQL_ROOT_PASSWORD.",
        )

    def check_ssl_settings(self):
        ok = (
            settings.SECURE_SSL_REDIRECT
            and settings.SESSION_COOKIE_SECURE
            and settings.CSRF_COOKIE_SECURE
            and settings.SECURE_HSTS_SECONDS > 0
        )
        return self.result(
            ok,
            "Cookies seguros, HTTPS redirect e HSTS configurados",
            "Defina SSL redirect, cookies seguros e HSTS apos confirmar HTTPS no dominio.",
        )

    def check_email_backend(self):
        backend = settings.EMAIL_BACKEND
        ok = backend == "django.core.mail.backends.smtp.EmailBackend" and bool(settings.EMAIL_HOST)
        return self.result(
            ok,
            "SMTP configurado",
            "Configure DJANGO_EMAIL_BACKEND como SMTP e informe DJANGO_EMAIL_HOST.",
        )

    def check_static_media_paths(self):
        expected = {
            str(settings.STATIC_ROOT),
            str(settings.MEDIA_ROOT),
            str(settings.PRIVATE_MEDIA_ROOT),
        }
        ok = expected == {"/app/staticfiles", "/app/media", "/app/private_media"}
        return self.result(
            ok,
            "Caminhos de static/media apontam para volumes do container",
            "Use /app/staticfiles, /app/media e /app/private_media no ambiente Docker.",
        )
