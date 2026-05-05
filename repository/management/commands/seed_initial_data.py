import getpass

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from repository.models import Building, Category, ProjectStatus, UserProfile
from repository.permissions import ROLE_ADMIN


INITIAL_CATEGORIES = [
    ("Obra nova", "#283E4C", "Projeto para nova edificação ou infraestrutura."),
    ("Reforma", "#C6543C", "Intervenção em espaço existente."),
    ("Layout/interiores", "#7A2632", "Organização espacial, mobiliário e interiores."),
    ("Paisagismo", "#A5B1BA", "Áreas externas, vegetação e ambiência paisagística."),
    ("Urbanismo", "#283E4C", "Desenho urbano, fluxos, acessos e implantação."),
    ("Projeto arquitetônico", "#010102", "Documentação arquitetônica principal."),
    ("Elétrico", "#C6543C", "Instalações elétricas e pontos de força."),
    ("Hidrossanitário", "#283E4C", "Sistemas hidráulicos, sanitários e drenagem."),
    ("Lógica/rede", "#7A2632", "Cabeamento estruturado, rede e telecomunicações."),
    ("Climatização", "#A5B1BA", "Sistemas de ar-condicionado e ventilação."),
    ("Acessibilidade", "#7A2632", "Adequações de acessibilidade e desenho universal."),
    ("Prevenção e combate a incêndio", "#C6543C", "Rotas, sinalização, extintores e segurança contra incêndio."),
    ("Comunicação visual/sinalização", "#7A2632", "Identidade ambiental, placas e orientação."),
    ("Compatibilização", "#010102", "Coordenação entre disciplinas de projeto."),
    ("As built", "#010102", "Registro da condição executada."),
    ("Estudo preliminar", "#A5B1BA", "Primeiros estudos e alternativas."),
    ("Anteprojeto", "#283E4C", "Desenvolvimento intermediário da solução."),
    ("Executivo", "#C6543C", "Documentação final para execução."),
]

INITIAL_PROJECT_STATUSES = [
    ("archived", "Arquivado", True),
    ("completed", "Concluído", True),
    ("in_progress", "Em andamento", False),
    ("draft", "Rascunho", False),
]

INITIAL_BUILDINGS = [
    "Áreas externas",
    "Biblioteca Setorial do CT",
    "Bloco Administrativo do CT",
    "Bloco CTA",
    "Bloco CTB",
    "Bloco CTC",
    "Bloco CTD",
    "Bloco CTE",
    "Bloco CTFG",
    "Bloco CTH",
    "Bloco CTJ",
    "Bloco CTKLM",
    "Bloco CTN",
    "Bloco CT-DEM LABES",
    "Bloco LABEME",
    "Bloco Laboratório de Vibrações do CT",
    "Bloco Multimídias do CT",
    "Bloco da Oficina Mecânica",
    "Bloco de Elétrica",
    "Bloco de Laboratório de Vibrações",
    "Bloco de Laboratórios de Engenharia de Alimentos",
    "Bloco do Ambiente de Professores do CT",
    "Bloco do LENHS",
    "Bloco do Laboratório Piloto de Química Industrial",
    "Bloco dos Centros Acadêmicos do CT",
    "CAs e Ejs do CT",
    "NEPEM",
    "NUPPA",
    "Todos as edificações",
]

LEGACY_CATEGORY_COLORS = {
    "#465C78",
    "#198754",
    "#0d6efd",
    "#2f9e44",
    "#5a7494",
    "#344759",
    "#fd7e14",
    "#0dcaf0",
    "#6f42c1",
    "#20c997",
    "#dc3545",
    "#f97316",
    "#6610f2",
    "#6c757d",
    "#1f2937",
}


class Command(BaseCommand):
    help = "Cria categorias iniciais e, opcionalmente, um usuário administrador."

    def add_arguments(self, parser):
        parser.add_argument("--create-admin", action="store_true", help="Cria um administrador inicial se ele não existir.")
        parser.add_argument("--username", default="admin", help="Nome de usuário do administrador inicial.")
        parser.add_argument("--password", default=None, help="Senha do administrador inicial.")
        parser.add_argument("--email", default="", help="E-mail do administrador inicial.")

    def handle(self, *args, **options):
        created_categories = 0
        updated_categories = 0
        created_statuses = 0
        for name, color, description in INITIAL_CATEGORIES:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={"color": color, "description": description},
            )
            created_categories += int(created)
            if not created and category.color in LEGACY_CATEGORY_COLORS:
                category.color = color
                category.save(update_fields=["color"])
                updated_categories += 1

        self.stdout.write(self.style.SUCCESS(f"Categorias criadas: {created_categories}"))
        if updated_categories:
            self.stdout.write(self.style.SUCCESS(f"Cores de categorias atualizadas: {updated_categories}"))

        for code, name, requires_end_date in INITIAL_PROJECT_STATUSES:
            _, created = ProjectStatus.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "requires_end_date": requires_end_date,
                },
            )
            created_statuses += int(created)
        self.stdout.write(self.style.SUCCESS(f"Status criados: {created_statuses}"))

        created_buildings = 0
        for name in INITIAL_BUILDINGS:
            _, created = Building.objects.get_or_create(name=name)
            created_buildings += int(created)
        self.stdout.write(self.style.SUCCESS(f"Edificações criadas: {created_buildings}"))

        if options["create_admin"]:
            password = options.get("password")
            if not password:
                password = getpass.getpass("Senha do administrador inicial: ")
                password_confirmation = getpass.getpass("Confirme a senha: ")
                if password != password_confirmation:
                    self.stderr.write(self.style.ERROR("As senhas não conferem."))
                    return
                if not password:
                    self.stderr.write(self.style.ERROR("A senha não pode ficar em branco."))
                    return
            User = get_user_model()
            user, created = User.objects.get_or_create(
                username=options["username"],
                defaults={"email": options["email"], "is_staff": True, "is_superuser": True},
            )
            if created:
                user.set_password(password)
                user.save()
                profile, _ = UserProfile.objects.get_or_create(user=user)
                profile.role = ROLE_ADMIN
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"Administrador criado: {user.username}"))
            else:
                self.stdout.write(self.style.WARNING(f"Usuário já existe: {user.username}"))
