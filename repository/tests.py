import shutil
from io import StringIO
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ProjectFileForm, ProjectForm, ProjectMemberForm
from .models import Building, Category, Person, Project, ProjectFile, ProjectMember, ProjectStatus, UserProfile, private_storage
from .permissions import ROLE_ADMIN, ROLE_READER, ROLE_TEAM


User = get_user_model()


def user_with_role(username, role):
    user = User.objects.create_user(username=username, password="senha-forte-123")
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = role
    profile.save()
    return user


class RepositoryAccessTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Reforma")
        self.public_project = Project.objects.create(
            name="Reforma do Laboratório",
            description="Adequação do laboratório para novas atividades acadêmicas.",
            visibility=Project.Visibility.PUBLIC,
            location="Bloco Administrativo do CT",
            sipac_url="https://sipac.ufpb.br/processo/123",
            start_date=date(2024, 3, 1),
            end_date=date(2026, 4, 16),
        )
        self.public_project.categories.add(self.category)
        self.restricted_project = Project.objects.create(
            name="Projeto Restrito",
            description="Registro técnico de acesso restrito.",
            visibility=Project.Visibility.RESTRICTED,
        )

    def test_public_catalog_hides_restricted_projects_from_visitors(self):
        response = self.client.get(reverse("repository:project_list"))

        self.assertContains(response, "Reforma do Laboratório")
        self.assertNotContains(response, "Projeto Restrito")
        self.assertNotContains(response, "Projetos encontrados")
        self.assertContains(response, "catalog-main")
        self.assertContains(response, "Repositório de Propostas da Assessoria de Projetos Urbanísticos e Infraestrutura")
        self.assertContains(response, "Projetos em fase preliminar")
        self.assertContains(response, "validados pela SINFRA")
        self.assertContains(response, 'data-catalog-sidebar-target="#projectFilters"')
        self.assertContains(response, "data-catalog-sidebar-toggle")
        self.assertContains(response, 'class="topbar-menu-button"')
        self.assertContains(response, 'class="offcanvas-lg offcanvas-start filter-drawer catalog-filter-sidebar"')
        self.assertNotContains(response, '<span>Filtros</span>')

    def test_project_card_uses_image_badges_and_icon_metadata(self):
        response = self.client.get(reverse("repository:project_list"))

        self.assertContains(response, 'class="project-image-badge project-years-badge"')
        self.assertContains(response, "2024 - 2026")
        self.assertContains(response, 'class="project-image-badge project-status-badge"')
        self.assertContains(response, "Em andamento")
        self.assertContains(response, 'class="project-location-meta"')
        self.assertContains(response, 'class="bi bi-building"')
        self.assertContains(response, "Bloco Administrativo do CT")
        self.assertContains(response, 'class="project-file-meta"')
        self.assertContains(response, 'class="bi bi-paperclip"')
        self.assertContains(response, 'class="project-sipac-meta"')
        self.assertContains(response, 'class="bi bi-link-45deg"')
        self.assertContains(response, "https://sipac.ufpb.br/processo/123")
        self.assertNotContains(response, "Atualizado")

    def test_catalog_filters_by_multiple_category_discipline_values(self):
        category = Category.objects.create(name="Elétrico")
        self.public_project.categories.add(category)
        other_project = Project.objects.create(
            name="Projeto de Paisagismo",
            description="Intervenção paisagística no entorno do centro.",
            visibility=Project.Visibility.PUBLIC,
        )

        response = self.client.get(
            reverse("repository:project_list"),
            {"category_discipline": [f"cat:{self.category.pk}", f"cat:{category.pk}"]},
        )

        self.assertContains(response, "Reforma do Laboratório")
        self.assertNotContains(response, other_project.name)
        self.assertContains(response, "Filtros ativos")
        self.assertContains(response, "Tipo de projeto")
        self.assertContains(response, 'class="active-filter-remove"', count=2)
        self.assertContains(response, f'?category_discipline=cat%3A{self.category.pk}')
        self.assertContains(response, f'?category_discipline=cat%3A{category.pk}')

    def test_authenticated_catalog_shows_restricted_projects(self):
        reader = user_with_role("leitor", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:project_list"))

        self.assertContains(response, "Reforma do Laboratório")
        self.assertContains(response, "Projeto Restrito")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("repository:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_authenticated_user_sees_dashboard_link_in_topbar(self):
        reader = user_with_role("leitor-dashboard-link", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:project_list"))

        self.assertContains(response, reverse("repository:dashboard"))
        self.assertContains(response, "Dashboard")

    def test_authenticated_user_can_open_dashboard_with_summary_metrics(self):
        reader = user_with_role("leitor-dashboard", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:dashboard"))
        content = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard de acompanhamento")
        self.assertContains(response, "Total de projetos")
        self.assertContains(response, "Projetos por ano")
        self.assertContains(response, "2024")
        self.assertContains(response, "Projetos por status")
        self.assertContains(response, "Em andamento")
        self.assertContains(response, "Tipos de projeto")
        self.assertContains(response, "Reforma")
        self.assertContains(response, "Projetos sem SIPAC")
        self.assertRegex(content, r'width: [0-9]+%')
        self.assertNotRegex(content, r'width: [0-9]+,[0-9]+%')

    def test_project_detail_uses_full_width_without_technical_memory_sidebar(self):
        response = self.client.get(self.public_project.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="detail-layout"')
        self.assertContains(response, 'class="detail-main detail-stack"')
        self.assertContains(response, 'id="overview"')
        self.assertContains(response, 'id="files"')
        self.assertContains(response, 'id="team"')
        self.assertContains(response, 'class="project-summary"')
        self.assertContains(response, "Processo SIPAC")
        self.assertContains(response, "Abrir processo")
        self.assertNotContains(response, "Memória técnica")
        self.assertNotContains(response, 'class="detail-side"')
        self.assertNotContains(response, 'id="project-tabs"')
        self.assertNotContains(response, 'class="tab-pane')

        content = response.content.decode()
        hero_start = content.index('class="project-hero')
        hero_end = content.index("</section>", hero_start)
        summary_start = content.index('class="project-summary"')
        info_labels = [
            "Data de início",
            "Data de conclusão",
            "Data de edição",
            "Status",
            "Edificação",
            "Demandante do projeto",
        ]
        info_positions = [content.index(f"<dt>{label}</dt>") for label in info_labels]
        self.assertNotIn(self.public_project.description, content[hero_start:hero_end])
        self.assertLess(summary_start, info_positions[0])
        self.assertEqual(info_positions, sorted(info_positions))

    def test_team_user_can_open_project_create_page(self):
        team = user_with_role("equipe", ROLE_TEAM)
        self.client.force_login(team)
        Building.objects.get_or_create(name="Bloco Administrativo do CT")

        response = self.client.get(reverse("repository:project_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo projeto")
        self.assertContains(response, 'class="form-panel project-form-panel"')
        self.assertContains(response, "Edificação")
        self.assertContains(response, "Bloco Administrativo do CT")
        self.assertContains(response, "Demandante do projeto")
        self.assertContains(response, "Link do processo no SIPAC")
        self.assertContains(response, "https://sipac.ufpb.br/...")
        self.assertContains(response, "project-date-status-row", count=3)
        self.assertContains(response, 'data-project-status="true"')
        self.assertContains(response, 'data-project-end-date="true"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'type="radio"')

    def test_project_form_requires_end_date_when_completed_or_archived(self):
        form = ProjectForm(
            data={
                "name": "Projeto concluído sem data",
                "description": "Registro de validação.",
                "status": Project.Status.COMPLETED,
                "visibility": Project.Visibility.PUBLIC,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("end_date", form.errors)

    def test_project_form_allows_completed_with_end_date(self):
        form = ProjectForm(
            data={
                "name": "Projeto concluído",
                "description": "Registro de validação.",
                "status": Project.Status.COMPLETED,
                "visibility": Project.Visibility.PUBLIC,
                "end_date": "2026-04-16",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_team_user_can_manage_project_options(self):
        team = user_with_role("equipe-opcoes", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.get(reverse("repository:options_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Opções do cadastro")
        self.assertContains(response, "Edificações")
        self.assertContains(response, "Status de projeto")
        self.assertContains(response, "Categorias")
        self.assertNotContains(response, "Ordem")

        response = self.client.post(
            reverse("repository:options_list"),
            {
                "option_kind": "building",
                "building-name": "Centro de Tecnologia - Bloco A",
                "building-description": "",
                "building-is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("repository:options_list"))
        self.assertTrue(Building.objects.filter(name="Centro de Tecnologia - Bloco A").exists())

    def test_team_user_can_edit_project_option_without_activation_email(self):
        team = user_with_role("equipe-edita-opcao", ROLE_TEAM)
        self.client.force_login(team)
        building = Building.objects.create(name="Bloco antigo", description="Nome antes da revisao.")

        response = self.client.post(
            reverse("repository:option_edit", args=["edificacoes", building.pk]),
            {
                "name": "Bloco revisado",
                "description": "Nome depois da revisao.",
                "is_active": "on",
            },
        )

        self.assertRedirects(response, reverse("repository:options_list"))
        building.refresh_from_db()
        self.assertEqual(building.name, "Bloco revisado")
        self.assertEqual(building.description, "Nome depois da revisao.")
        self.assertEqual(len(mail.outbox), 0)

    def test_project_create_uses_saved_building_and_dynamic_status(self):
        team = user_with_role("equipe-projeto", ROLE_TEAM)
        self.client.force_login(team)
        building = Building.objects.create(name="Laboratório de Conforto Ambiental")
        status = ProjectStatus.objects.create(code="licitacao", name="Em licitação")

        response = self.client.post(
            reverse("repository:project_create"),
            {
                "name": "Adequação do laboratório",
                "description": "Projeto com opções persistentes.",
                "building": str(building.pk),
                "requested_by": "Direção de Centro",
                "sipac_url": "https://sipac.ufpb.br/processo/456",
                "status": status.code,
                "visibility": Project.Visibility.PUBLIC,
            },
        )

        project = Project.objects.get(name="Adequação do laboratório")
        self.assertRedirects(response, project.get_absolute_url())
        self.assertEqual(project.building, building)
        self.assertEqual(project.location, building.name)
        self.assertEqual(project.sipac_url, "https://sipac.ufpb.br/processo/456")
        self.assertEqual(project.status, status.code)
        self.assertEqual(project.status_label, "Em licitação")

    def test_reader_cannot_open_people_management(self):
        reader = user_with_role("leitor2", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:people_list"))

        self.assertEqual(response.status_code, 403)

    def test_admin_can_open_user_management(self):
        admin = user_with_role("admin", ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.get(reverse("repository:users_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Usuários")

    def test_user_management_shows_view_edit_delete_actions(self):
        admin = user_with_role("admin-acoes", ROLE_ADMIN)
        managed_user = user_with_role("usuario-comum", ROLE_READER)
        self.client.force_login(admin)

        response = self.client.get(reverse("repository:users_list"))

        self.assertContains(response, "Ações")
        self.assertContains(response, reverse("repository:user_detail", args=[managed_user.pk]))
        self.assertContains(response, reverse("repository:user_edit", args=[managed_user.pk]))
        self.assertContains(response, reverse("repository:user_delete", args=[managed_user.pk]))
        self.assertContains(response, "bi-eye")
        self.assertContains(response, "bi-pencil")
        self.assertContains(response, "bi-trash")

    def test_admin_can_view_user_detail(self):
        admin = user_with_role("admin-ver-usuario", ROLE_ADMIN)
        managed_user = user_with_role("usuario-detalhe", ROLE_READER)
        managed_user.email = "usuario@example.com"
        managed_user.save(update_fields=["email"])
        self.client.force_login(admin)

        response = self.client.get(reverse("repository:user_detail", args=[managed_user.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dados do usuário")
        self.assertContains(response, "usuario-detalhe")
        self.assertContains(response, "usuario@example.com")

    def test_admin_can_delete_regular_user(self):
        admin = user_with_role("admin-exclui", ROLE_ADMIN)
        managed_user = user_with_role("usuario-apagar", ROLE_READER)
        self.client.force_login(admin)

        response = self.client.post(reverse("repository:user_delete", args=[managed_user.pk]))

        self.assertRedirects(response, reverse("repository:users_list"))
        self.assertFalse(User.objects.filter(pk=managed_user.pk).exists())

    def test_admin_cannot_delete_own_user(self):
        admin = user_with_role("admin-nao-autoexclui", ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.post(reverse("repository:user_delete", args=[admin.pk]))

        self.assertRedirects(response, reverse("repository:users_list"))
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())

    def test_user_create_sends_activation_link_without_password_fields(self):
        admin = user_with_role("admin-convida", ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.get(reverse("repository:user_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enviar convite")
        self.assertNotContains(response, "password1")
        self.assertNotContains(response, "password2")

        response = self.client.post(
            reverse("repository:user_create"),
            {
                "username": "novo-convidado",
                "first_name": "Novo",
                "last_name": "Convidado",
                "email": "novo.convidado@example.com",
                "role": ROLE_READER,
            },
        )

        self.assertRedirects(response, reverse("repository:users_list"))
        invited_user = User.objects.get(username="novo-convidado")
        self.assertFalse(invited_user.is_active)
        self.assertFalse(invited_user.has_usable_password())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/usuarios/ativar/", mail.outbox[0].body)
        self.assertIn("novo.convidado@example.com", mail.outbox[0].to)

    def test_user_activation_sets_password_and_activates_user(self):
        user = User.objects.create_user(
            username="usuario-ativar",
            first_name="Usuario",
            last_name="Ativar",
            email="ativar@example.com",
            is_active=False,
        )
        user.set_unusable_password()
        user.save()
        from .views import build_user_activation_token

        response = self.client.post(
            reverse("repository:user_activate", args=[build_user_activation_token(user)]),
            {
                "new_password1": "Senha-forte-123",
                "new_password2": "Senha-forte-123",
            },
        )

        self.assertRedirects(response, reverse("repository:project_list"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("Senha-forte-123"))

    def test_admin_links_move_to_topbar_dropdown(self):
        admin = user_with_role("admin2", ROLE_ADMIN)
        self.client.force_login(admin)

        response = self.client.get(reverse("repository:project_list"))

        self.assertContains(response, 'class="dropdown-menu dropdown-menu-end topbar-dropdown"')
        self.assertContains(response, "Pessoas")
        self.assertContains(response, "Usuários")
        self.assertContains(response, "Admin Django")
        self.assertNotContains(response, 'class="sidebar-link"')

    def test_team_user_sees_new_member_action_without_embedded_form(self):
        team = user_with_role("equipe-membro", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.get(self.public_project.get_absolute_url())

        self.assertContains(response, "Equipe de elaboração")
        self.assertContains(response, reverse("repository:project_member_add", args=[self.public_project.slug]))
        self.assertContains(response, "Novo Membro")
        self.assertNotContains(response, "Adicionar integrante")

    def test_team_user_can_open_project_member_create_page(self):
        team = user_with_role("equipe-novo-membro", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.get(reverse("repository:project_member_add", args=[self.public_project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo membro")
        self.assertContains(response, "Salvar membro")
        self.assertNotContains(response, "Ordem *")

    def test_project_member_form_omits_order(self):
        form = ProjectMemberForm()

        self.assertNotIn("order", form.fields)

    def test_team_user_can_create_project_member_from_page(self):
        team = user_with_role("equipe-cria-membro", ROLE_TEAM)
        self.client.force_login(team)
        person = Person.objects.create(name="Alison", function="Arquiteto")

        response = self.client.post(
            reverse("repository:project_member_add", args=[self.public_project.slug]),
            {
                "person": str(person.pk),
                "role": ProjectMember.Role.ARCHITECTURE,
                "responsibility": "Projeto arquitetônico",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{self.public_project.get_absolute_url()}#team")
        membership = ProjectMember.objects.get(project=self.public_project, person=person)
        self.assertEqual(membership.role, ProjectMember.Role.ARCHITECTURE)
        self.assertEqual(membership.responsibility, "Projeto arquitetônico")
        self.assertEqual(membership.order, 0)

    def test_reader_cannot_open_project_member_create_page(self):
        reader = user_with_role("leitor-novo-membro", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:project_member_add", args=[self.public_project.slug]))

        self.assertEqual(response.status_code, 403)


class ProjectFileDownloadTests(TestCase):
    def setUp(self):
        self.tmpdir = Path(settings.BASE_DIR) / ".test_private_media"
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        self.tmpdir.mkdir(parents=True, exist_ok=True)
        self.override = override_settings(PRIVATE_MEDIA_ROOT=self.tmpdir)
        self.override.enable()
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)

        self.project = Project.objects.create(
            name="Bloco Administrativo",
            status=Project.Status.COMPLETED,
            end_date=date(2026, 4, 16),
            description="Projeto arquitetônico do bloco administrativo.",
        )
        uploaded = SimpleUploadedFile("planta.pdf", b"conteudo-pdf", content_type="application/pdf")
        self.project_file = ProjectFile.objects.create(
            project=self.project,
            title="Planta baixa",
            file=uploaded,
            file_type=ProjectFile.FileType.PDF,
            discipline=ProjectFile.Discipline.ARCHITECTURE,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        private_storage.__dict__.pop("base_location", None)
        private_storage.__dict__.pop("location", None)

    def test_anonymous_can_download_public_project_file(self):
        response = self.client.get(reverse("repository:project_file_download", args=[self.project_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="planta.pdf"')

    def test_anonymous_cannot_download_public_project_file_before_completion(self):
        project = Project.objects.create(
            name="Projeto publico em andamento",
            description="Arquivo publico visivel, mas ainda nao finalizado.",
            visibility=Project.Visibility.PUBLIC,
            status=Project.Status.IN_PROGRESS,
        )
        project_file = ProjectFile.objects.create(
            project=project,
            title="Estudo preliminar",
            file=SimpleUploadedFile("estudo.pdf", b"conteudo-preliminar", content_type="application/pdf"),
            file_type=ProjectFile.FileType.PDF,
            discipline=ProjectFile.Discipline.ARCHITECTURE,
        )

        response = self.client.get(reverse("repository:project_file_download", args=[project_file.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("login"))

    def test_anonymous_download_of_restricted_project_file_redirects_to_login(self):
        restricted_project = Project.objects.create(
            name="Projeto restrito com arquivo",
            description="Arquivo protegido por login.",
            visibility=Project.Visibility.RESTRICTED,
        )
        restricted_file = ProjectFile.objects.create(
            project=restricted_project,
            title="Planta restrita",
            file=SimpleUploadedFile("restrito.pdf", b"conteudo-restrito", content_type="application/pdf"),
            file_type=ProjectFile.FileType.PDF,
            discipline=ProjectFile.Discipline.ARCHITECTURE,
        )

        response = self.client.get(reverse("repository:project_file_download", args=[restricted_file.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("login"))

    def test_authenticated_reader_can_download_project_file(self):
        reader = user_with_role("leitor", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:project_file_download", args=[self.project_file.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="planta.pdf"')

    def test_project_detail_shows_public_file_metadata_to_anonymous_user(self):
        response = self.client.get(self.project.get_absolute_url())

        self.assertContains(response, "Planta baixa")
        self.assertContains(response, "planta.pdf")
        self.assertContains(response, reverse("repository:project_file_download", args=[self.project_file.pk]))
        self.assertNotContains(response, "Entrar para baixar")

    def test_project_detail_shows_file_metadata_under_title(self):
        reader = user_with_role("leitor-arquivos", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(self.project.get_absolute_url())

        self.assertContains(response, 'class="table align-middle repository-table project-files-table"')
        self.assertContains(response, 'class="project-files-col-main"')
        self.assertContains(response, 'class="project-files-col-equal"', count=5)
        self.assertContains(response, "<th>Data</th>", html=True)
        self.assertContains(response, '<th class="text-end">Ações</th>', html=True)
        self.assertNotContains(response, "<th>Disciplina</th>", html=True)
        self.assertNotContains(response, "<th>Status</th>", html=True)
        self.assertContains(response, 'class="project-file-cell"')
        self.assertContains(response, 'class="project-file-title"')
        self.assertContains(response, "Planta baixa")
        self.assertContains(response, 'class="project-file-description"')
        self.assertContains(response, "planta.pdf · 0.0 MB")

        self.assertContains(response, self.project_file.uploaded_at.strftime("%d/%m/%Y"))

    def test_team_user_sees_file_edit_action_on_project_detail(self):
        team = user_with_role("equipe-arquivo", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.get(self.project.get_absolute_url())

        self.assertContains(response, reverse("repository:project_file_upload", args=[self.project.slug]))
        self.assertContains(response, "Novo arquivo")
        self.assertNotContains(response, "Anexar nova versão ou arquivo")
        self.assertContains(response, reverse("repository:project_file_edit", args=[self.project_file.pk]))
        self.assertContains(response, 'title="Editar arquivo"')
        self.assertContains(response, reverse("repository:project_file_delete", args=[self.project_file.pk]))
        self.assertContains(response, 'title="Excluir arquivo"')

    def test_team_user_can_open_project_file_create_page(self):
        team = user_with_role("equipe-novo-arquivo", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.get(reverse("repository:project_file_upload", args=[self.project.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novo arquivo")
        self.assertContains(response, "Salvar arquivo")
        self.assertNotContains(response, "Arquivo atual")
        self.assertNotContains(response, "Disciplina *")
        self.assertNotContains(response, "Status *")

    def test_project_file_form_omits_discipline_status_and_limits_description(self):
        form = ProjectFileForm()

        self.assertNotIn("discipline", form.fields)
        self.assertNotIn("status", form.fields)
        self.assertEqual(form.fields["description"].max_length, 140)
        self.assertEqual(form.fields["description"].widget.attrs["maxlength"], "140")

    def test_team_user_can_create_project_file_from_page(self):
        team = user_with_role("equipe-cria-arquivo", ROLE_TEAM)
        self.client.force_login(team)
        uploaded = SimpleUploadedFile("fachada-leste.dwg", b"conteudo-dwg", content_type="application/acad")

        response = self.client.post(
            reverse("repository:project_file_upload", args=[self.project.slug]),
            {
                "title": "Projeto de Paisagismo Fachada Leste",
                "file": uploaded,
                "file_type": ProjectFile.FileType.DWG,
                "version": "v1",
                "description": "Arquivo CAD da fachada leste.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{self.project.get_absolute_url()}#files")
        created_file = ProjectFile.objects.get(title="Projeto de Paisagismo Fachada Leste")
        self.assertEqual(created_file.project, self.project)
        self.assertEqual(created_file.uploaded_by, team)
        self.assertEqual(created_file.original_filename, "fachada-leste.dwg")
        self.assertEqual(created_file.discipline, ProjectFile.Discipline.ARCHITECTURE)
        self.assertEqual(created_file.status, ProjectFile.Status.CURRENT)

    def test_team_user_can_edit_project_file_metadata(self):
        team = user_with_role("equipe-edita-arquivo", ROLE_TEAM)
        self.client.force_login(team)

        response = self.client.post(
            reverse("repository:project_file_edit", args=[self.project_file.pk]),
            {
                "title": "Planta baixa revisada",
                "file_type": ProjectFile.FileType.PDF,
                "version": "v2",
                "description": "Arquivo revisado pela equipe.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{self.project.get_absolute_url()}#files")
        self.project_file.refresh_from_db()
        self.assertEqual(self.project_file.title, "Planta baixa revisada")
        self.assertEqual(self.project_file.version, "v2")

    def test_reader_cannot_edit_project_file(self):
        reader = user_with_role("leitor-arquivo", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.get(reverse("repository:project_file_edit", args=[self.project_file.pk]))

        self.assertEqual(response.status_code, 403)

    def test_team_user_can_delete_project_file(self):
        team = user_with_role("equipe-exclui-arquivo", ROLE_TEAM)
        self.client.force_login(team)
        stored_path = Path(private_storage.path(self.project_file.file.name))

        response = self.client.post(reverse("repository:project_file_delete", args=[self.project_file.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], f"{self.project.get_absolute_url()}#files")
        self.assertFalse(ProjectFile.objects.filter(pk=self.project_file.pk).exists())
        self.assertFalse(stored_path.exists())

    def test_reader_cannot_delete_project_file(self):
        reader = user_with_role("leitor-exclui-arquivo", ROLE_READER)
        self.client.force_login(reader)

        response = self.client.post(reverse("repository:project_file_delete", args=[self.project_file.pk]))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ProjectFile.objects.filter(pk=self.project_file.pk).exists())


class SeedInitialDataTests(TestCase):
    def test_seed_initial_data_creates_categories(self):
        call_command("seed_initial_data")

        self.assertGreaterEqual(Category.objects.count(), 18)
        self.assertTrue(Category.objects.filter(name="Compatibilização").exists())
        self.assertTrue(Category.objects.filter(name="Reforma", color="#C6543C").exists())
        self.assertTrue(ProjectStatus.objects.filter(code="completed", requires_end_date=True).exists())
        self.assertTrue(Building.objects.filter(name="Biblioteca Setorial do CT").exists())

    def test_seed_initial_data_updates_legacy_category_colors(self):
        category = Category.objects.create(name="Reforma", color="#198754")

        call_command("seed_initial_data")
        category.refresh_from_db()

        self.assertEqual(category.color, "#C6543C")

    def test_seed_initial_data_preserves_custom_category_colors(self):
        category = Category.objects.create(name="Reforma", color="#123456")

        call_command("seed_initial_data")
        category.refresh_from_db()

        self.assertEqual(category.color, "#123456")


class AccountRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="marcel",
            email="marcel@example.com",
            password="senha-antiga-123",
            is_active=True,
        )

    def test_login_page_links_to_password_and_username_recovery(self):
        response = self.client.get(reverse("login"))

        self.assertContains(response, reverse("password_reset"))
        self.assertContains(response, reverse("repository:username_reminder"))
        self.assertContains(response, "Esqueci minha senha")
        self.assertContains(response, "Esqueci meu usuário")
        self.assertContains(response, "Usuário ou e-mail")

    def test_login_accepts_registered_email(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": self.user.email,
                "password": "senha-antiga-123",
            },
        )

        self.assertRedirects(response, reverse("repository:project_list"))

    def test_password_reset_sends_email_with_reset_link(self):
        response = self.client.post(reverse("password_reset"), {"email": self.user.email})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/senha/redefinir/", mail.outbox[0].body)

    def test_username_reminder_sends_username_by_email(self):
        response = self.client.post(reverse("repository:username_reminder"), {"email": self.user.email})

        self.assertRedirects(response, reverse("repository:username_reminder_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("marcel", mail.outbox[0].body)

    def test_username_reminder_does_not_reveal_unknown_email(self):
        response = self.client.post(reverse("repository:username_reminder"), {"email": "naoexiste@example.com"})

        self.assertRedirects(response, reverse("repository:username_reminder_done"))
        self.assertEqual(len(mail.outbox), 0)


class HealthcheckTests(TestCase):
    def test_healthcheck_returns_ok_payload(self):
        response = self.client.get(reverse("repository:healthcheck"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})


class ProductionReadinessCommandTests(TestCase):
    def test_command_reports_pending_items_in_local_environment(self):
        output = StringIO()

        call_command("check_production_ready", stdout=output)

        self.assertIn("Verificacao de prontidao para producao", output.getvalue())
        self.assertIn("PENDENTE", output.getvalue())

    @override_settings(
        DEBUG=False,
        SECRET_KEY="prod-secret-key-0123456789abcdefghijklmnopqrstuvwxyz-CT",
        ALLOWED_HOSTS=["projetos.ct.ufpb.br"],
        CSRF_TRUSTED_ORIGINS=["https://projetos.ct.ufpb.br"],
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "NAME": "repo_arquitetonico_prod",
                "USER": "repo_arquitetonico_user",
                "PASSWORD": "senha-forte-usuario",
                "HOST": "mysql",
                "PORT": "3306",
            }
        },
        SECURE_SSL_REDIRECT=True,
        SESSION_COOKIE_SECURE=True,
        CSRF_COOKIE_SECURE=True,
        SECURE_HSTS_SECONDS=31536000,
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        EMAIL_HOST="smtp.ct.ufpb.br",
        STATIC_ROOT="/app/staticfiles",
        MEDIA_ROOT="/app/media",
        PRIVATE_MEDIA_ROOT="/app/private_media",
    )
    def test_command_accepts_production_like_environment(self):
        output = StringIO()
        env = {
            "MYSQL_DATABASE": "repo_arquitetonico_prod",
            "MYSQL_USER": "repo_arquitetonico_user",
            "MYSQL_PASSWORD": "senha-forte-usuario",
            "MYSQL_ROOT_PASSWORD": "senha-forte-root",
        }

        with patch.dict("os.environ", env, clear=False):
            call_command("check_production_ready", "--strict", stdout=output)

        self.assertIn("Ambiente pronto para validacao de producao.", output.getvalue())
        self.assertNotIn("PENDENTE", output.getvalue())
