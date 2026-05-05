import mimetypes
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import ExtractYear
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from .forms import (
    BuildingForm,
    CategoryForm,
    ManagedUserCreateForm,
    ManagedUserUpdateForm,
    PersonForm,
    ProjectFileForm,
    ProjectFilterForm,
    ProjectForm,
    ProjectImageForm,
    ProjectMemberForm,
    ProjectStatusForm,
    UsernameReminderForm,
)
from .models import Building, Category, Person, Project, ProjectFile, ProjectImage, ProjectMember, ProjectStatus
from .permissions import is_admin_user, is_team_user, require_admin, require_team


User = get_user_model()


def build_dashboard_bars(items):
    max_value = max((item["value"] for item in items), default=0)
    for item in items:
        if max_value == 0:
            item["width"] = "0"
        else:
            item["width"] = str(round((item["value"] / max_value) * 100))
    return items


def healthcheck(_request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})


def username_reminder(request):
    form = UsernameReminderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip()
        users = User.objects.filter(email__iexact=email, is_active=True).order_by("username")
        if users.exists():
            body = render_to_string(
                "registration/username_reminder_email.txt",
                {
                    "users": users,
                    "login_url": request.build_absolute_uri(reverse("login")),
                },
            )
            send_mail(
                "Seu usuário no Repositório de Projetos Arquitetônicos",
                body,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
        return redirect("repository:username_reminder_done")
    return render(request, "registration/username_reminder_form.html", {"form": form})


def username_reminder_done(request):
    return render(request, "registration/username_reminder_done.html")


def visible_projects_for(user):
    projects = Project.objects.select_related("building", "created_by").prefetch_related("categories", "memberships__person")
    if user.is_authenticated:
        return projects
    return projects.filter(visibility=Project.Visibility.PUBLIC)


def project_filter_remove_url(query_params, field_name, value=None):
    updated_params = query_params.copy()
    if value is None:
        updated_params.pop(field_name, None)
    else:
        remaining_values = [current for current in updated_params.getlist(field_name) if current != value]
        if remaining_values:
            updated_params.setlist(field_name, remaining_values)
        else:
            updated_params.pop(field_name, None)

    encoded_params = updated_params.urlencode()
    base_url = reverse("repository:project_list")
    if encoded_params:
        return f"{base_url}?{encoded_params}"
    return base_url


def active_project_filter_tags(query_params, data):
    tags = []
    query = data.get("q")
    if query:
        tags.append({"label": "Busca", "value": query, "remove_url": project_filter_remove_url(query_params, "q")})

    category_discipline = data.get("category_discipline") or []
    category_ids = [
        value.removeprefix("cat:")
        for value in category_discipline
        if value.startswith("cat:") and value.removeprefix("cat:").isdigit()
    ]
    category_map = {
        str(category.pk): category.name
        for category in Category.objects.filter(pk__in=category_ids)
    }
    discipline_map = dict(ProjectFile.Discipline.choices)
    for value in category_discipline:
        if value.startswith("cat:"):
            category_name = category_map.get(value.removeprefix("cat:"))
            if category_name:
                tags.append({
                    "label": "Tipo de projeto",
                    "value": category_name,
                    "remove_url": project_filter_remove_url(query_params, "category_discipline", value),
                })
        elif value.startswith("disc:"):
            discipline_name = discipline_map.get(value.removeprefix("disc:"))
            if discipline_name:
                tags.append({
                    "label": "Tipo de projeto",
                    "value": discipline_name,
                    "remove_url": project_filter_remove_url(query_params, "category_discipline", value),
                })

    if data.get("status"):
        status = ProjectStatus.objects.filter(code=data["status"]).first()
        tags.append({
            "label": "Status",
            "value": status.name if status else dict(Project.Status.choices).get(data["status"], data["status"]),
            "remove_url": project_filter_remove_url(query_params, "status"),
        })
    if data.get("building"):
        tags.append({"label": "Edificação", "value": data["building"].name, "remove_url": project_filter_remove_url(query_params, "building")})
    if data.get("requested_by"):
        tags.append({"label": "Demandante", "value": data["requested_by"], "remove_url": project_filter_remove_url(query_params, "requested_by")})
    return tags


def project_list(request):
    filters = ProjectFilterForm(request.GET or None)
    projects = visible_projects_for(request.user).annotate(file_count=Count("files", distinct=True))
    active_filters = []

    if filters.is_valid():
        data = filters.cleaned_data
        active_filters = active_project_filter_tags(request.GET, data)
        query = data.get("q")
        if query:
            projects = projects.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(location__icontains=query)
                | Q(building__name__icontains=query)
                | Q(requested_by__icontains=query)
                | Q(categories__name__icontains=query)
                | Q(memberships__person__name__icontains=query)
                | Q(files__title__icontains=query)
            )
        category_discipline = data.get("category_discipline") or []
        category_ids = [value.removeprefix("cat:") for value in category_discipline if value.startswith("cat:")]
        disciplines = [value.removeprefix("disc:") for value in category_discipline if value.startswith("disc:")]
        if category_ids or disciplines:
            category_discipline_filter = Q()
            if category_ids:
                category_discipline_filter |= Q(categories__id__in=category_ids)
            if disciplines:
                category_discipline_filter |= Q(files__discipline__in=disciplines)
            projects = projects.filter(category_discipline_filter)
        if data.get("status"):
            projects = projects.filter(status=data["status"])
        if data.get("building"):
            projects = projects.filter(building=data["building"])
        if data.get("requested_by"):
            projects = projects.filter(requested_by__icontains=data["requested_by"])

    projects = projects.distinct()
    context = {
        "filters": filters,
        "active_filters": active_filters,
        "projects": projects,
        "can_edit": is_team_user(request.user),
    }
    return render(request, "repository/project_list.html", context)


def project_detail(request, slug):
    project = get_object_or_404(
        Project.objects.select_related("building").prefetch_related("categories", "memberships__person", "files__responsible"),
        slug=slug,
    )
    if project.visibility == Project.Visibility.RESTRICTED and not request.user.is_authenticated:
        messages.info(request, "Faça login para visualizar este projeto restrito.")
        return redirect("login")

    files = project.files.select_related("responsible", "uploaded_by")
    images = project.images.all()
    context = {
        "project": project,
        "files": files,
        "images": images,
        "can_edit": is_team_user(request.user),
        "can_download": request.user.is_authenticated or project.allows_public_download,
    }
    return render(request, "repository/project_detail.html", context)


@login_required
def dashboard(request):
    recent_cutoff = timezone.now() - timedelta(days=30)
    summary = Project.objects.aggregate(
        total_projects=Count("id", distinct=True),
        public_projects=Count("id", filter=Q(visibility=Project.Visibility.PUBLIC), distinct=True),
        restricted_projects=Count("id", filter=Q(visibility=Project.Visibility.RESTRICTED), distinct=True),
        with_sipac=Count("id", filter=Q(sipac_url__gt=""), distinct=True),
        with_files=Count("id", filter=Q(files__isnull=False), distinct=True),
        with_images=Count("id", filter=Q(images__isnull=False), distinct=True),
        without_cover=Count("id", filter=Q(cover_image=""), distinct=True),
        without_start_date=Count("id", filter=Q(start_date__isnull=True), distinct=True),
        updated_recently=Count("id", filter=Q(updated_at__gte=recent_cutoff), distinct=True),
    )

    project_rollup = Project.objects.annotate(
        file_count=Count("files", distinct=True),
        team_count=Count("memberships", distinct=True),
        image_count=Count("images", distinct=True),
    )
    project_rollup_list = list(project_rollup)
    total_projects = summary["total_projects"] or 0

    summary["without_files"] = sum(1 for project in project_rollup_list if project.file_count == 0)
    summary["without_team"] = sum(1 for project in project_rollup_list if project.team_count == 0)
    summary["without_sipac"] = total_projects - (summary["with_sipac"] or 0)
    summary["avg_files"] = round(sum(project.file_count for project in project_rollup_list) / total_projects, 1) if total_projects else 0
    summary["avg_team_members"] = round(sum(project.team_count for project in project_rollup_list) / total_projects, 1) if total_projects else 0

    yearly_projects = list(
        Project.objects.exclude(start_date__isnull=True)
        .annotate(year=ExtractYear("start_date"))
        .values("year")
        .annotate(total=Count("id"))
        .order_by("year")
    )
    yearly_bars = build_dashboard_bars([{"label": str(item["year"]), "value": item["total"]} for item in yearly_projects if item["year"]])
    projects_without_year = Project.objects.filter(start_date__isnull=True).count()
    if projects_without_year:
        yearly_bars = build_dashboard_bars(yearly_bars + [{"label": "Sem ano", "value": projects_without_year}])

    status_names = dict(Project.Status.choices)
    status_names.update({status.code: status.name for status in ProjectStatus.objects.all()})
    status_bars = build_dashboard_bars(
        [
            {"label": status_names.get(item["status"], item["status"]), "value": item["total"]}
            for item in Project.objects.values("status").annotate(total=Count("id")).order_by("-total", "status")
        ]
    )

    category_bars = build_dashboard_bars(
        [
            {"label": category.name, "value": category.total}
            for category in Category.objects.annotate(total=Count("projects", distinct=True)).filter(total__gt=0).order_by("-total", "name")[:10]
        ]
    )
    building_bars = build_dashboard_bars(
        [
            {"label": building.name, "value": building.total}
            for building in Building.objects.annotate(total=Count("projects", distinct=True)).filter(total__gt=0).order_by("-total", "name")[:10]
        ]
    )
    requested_by_bars = build_dashboard_bars(
        [
            {"label": item["requested_by"], "value": item["total"]}
            for item in Project.objects.exclude(requested_by="").values("requested_by").annotate(total=Count("id")).order_by("-total", "requested_by")[:10]
        ]
    )

    recent_projects = project_rollup.order_by("-updated_at", "name")[:6]
    projects_without_files = project_rollup.filter(file_count=0).order_by("-updated_at", "name")[:5]
    projects_without_team = project_rollup.filter(team_count=0).order_by("-updated_at", "name")[:5]
    projects_without_sipac = project_rollup.filter(sipac_url="").order_by("-updated_at", "name")[:5]

    context = {
        "summary": summary,
        "yearly_bars": yearly_bars,
        "status_bars": status_bars,
        "category_bars": category_bars,
        "building_bars": building_bars,
        "requested_by_bars": requested_by_bars,
        "recent_projects": recent_projects,
        "projects_without_files": projects_without_files,
        "projects_without_team": projects_without_team,
        "projects_without_sipac": projects_without_sipac,
    }
    return render(request, "repository/dashboard.html", context)


@login_required
def project_create(request):
    require_team(request.user)
    form = ProjectForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.created_by = request.user
        project.updated_by = request.user
        project.save()
        form.save_m2m()
        messages.success(request, "Projeto cadastrado com sucesso.")
        return redirect(project)
    return render(request, "repository/project_form.html", {"form": form, "title": "Novo projeto"})


@login_required
def project_edit(request, slug):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    form = ProjectForm(request.POST or None, request.FILES or None, instance=project)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.updated_by = request.user
        project.save()
        form.save_m2m()
        messages.success(request, "Projeto atualizado.")
        return redirect(project)
    return render(request, "repository/project_form.html", {"form": form, "project": project, "title": "Editar projeto"})


@login_required
def project_file_upload(request, slug):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    form = ProjectFileForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        project_file = form.save(commit=False)
        project_file.project = project
        project_file.uploaded_by = request.user
        project_file.save()
        messages.success(request, "Arquivo anexado ao projeto.")
        return redirect(f"{project.get_absolute_url()}#files")
    return render(
        request,
        "repository/project_file_form.html",
        {
            "form": form,
            "project": project,
            "project_file": None,
            "title": "Novo arquivo",
        },
    )


@login_required
def project_file_edit(request, pk):
    require_team(request.user)
    project_file = get_object_or_404(ProjectFile.objects.select_related("project"), pk=pk)
    form = ProjectFileForm(request.POST or None, request.FILES or None, instance=project_file)
    if request.method == "POST" and form.is_valid():
        edited_file = form.save(commit=False)
        replacement = request.FILES.get("file")
        if replacement:
            edited_file.original_filename = Path(replacement.name).name
            edited_file.size = replacement.size
        edited_file.save()
        messages.success(request, "Arquivo atualizado.")
        return redirect(f"{project_file.project.get_absolute_url()}#files")
    return render(
        request,
        "repository/project_file_form.html",
        {
            "form": form,
            "project": project_file.project,
            "project_file": project_file,
            "title": "Editar arquivo",
        },
    )


@login_required
def project_file_delete(request, pk):
    require_team(request.user)
    project_file = get_object_or_404(ProjectFile.objects.select_related("project"), pk=pk)
    project_url = project_file.project.get_absolute_url()
    if request.method != "POST":
        raise PermissionDenied("Use POST para excluir arquivos.")

    title = project_file.title
    if project_file.file:
        project_file.file.delete(save=False)
    project_file.delete()
    messages.success(request, f"Arquivo excluído: {title}.")
    return redirect(f"{project_url}#files")


@login_required
def project_member_add(request, slug):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    form = ProjectMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        membership = form.save(commit=False)
        membership.project = project
        membership.save()
        messages.success(request, "Integrante adicionado à equipe do projeto.")
        return redirect(f"{project.get_absolute_url()}#team")
    return render(
        request,
        "repository/project_member_form.html",
        {
            "form": form,
            "project": project,
            "title": "Novo membro",
        },
    )


@login_required
def project_member_delete(request, slug, pk):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    membership = get_object_or_404(ProjectMember, pk=pk, project=project)
    if request.method != "POST":
        raise PermissionDenied("Use POST para remover integrantes.")
    membership.delete()
    messages.success(request, "Integrante removido da equipe do projeto.")
    return redirect(project)


@login_required
def project_image_upload(request, slug):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    if request.method == "POST":
        files = request.FILES.getlist("image")
        captions = request.POST.getlist("caption")
        saved = 0
        for i, f in enumerate(files):
            caption = captions[i] if i < len(captions) else ""
            img = ProjectImage(project=project, caption=caption, order=project.images.count() + i)
            img.image.save(f.name, f, save=True)
            saved += 1
        if saved:
            messages.success(request, f"{saved} imagem{'ns' if saved > 1 else ''} adicionada{'s' if saved > 1 else ''}.")
        return redirect(f"{project.get_absolute_url()}#gallery")
    form = ProjectImageForm()
    return render(request, "repository/project_image_upload.html", {"form": form, "project": project})


@login_required
def project_image_delete(request, slug, pk):
    require_team(request.user)
    project = get_object_or_404(Project, slug=slug)
    image = get_object_or_404(ProjectImage, pk=pk, project=project)
    if request.method != "POST":
        raise PermissionDenied("Use POST para excluir imagens.")
    if image.image:
        image.image.delete(save=False)
    image.delete()
    messages.success(request, "Imagem removida.")
    return redirect(f"{project.get_absolute_url()}#gallery")


def project_file_download(request, pk):
    project_file = get_object_or_404(ProjectFile.objects.select_related("project"), pk=pk)
    if not request.user.is_authenticated and not project_file.project.allows_public_download:
        messages.info(request, "Faça login para baixar arquivos internos ou aguarde a finalização do projeto.")
        return redirect("login")
    if not project_file.file:
        raise Http404("Arquivo não encontrado.")

    filename = project_file.original_filename or Path(project_file.file.name).name
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(project_file.file.open("rb"), as_attachment=True, filename=filename, content_type=content_type)
    return response


@login_required
def people_list(request):
    require_team(request.user)
    query = request.GET.get("q", "").strip()
    people = Person.objects.select_related("user").annotate(project_count=Count("projects", distinct=True))
    if query:
        people = people.filter(
            Q(name__icontains=query)
            | Q(function__icontains=query)
            | Q(institutional_link__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "repository/people_list.html", {"people": people, "query": query})


@login_required
def options_list(request):
    require_team(request.user)
    forms = {
        "building": BuildingForm(prefix="building"),
        "status": ProjectStatusForm(prefix="status"),
        "category": CategoryForm(prefix="category"),
    }
    if request.method == "POST":
        option_kind = request.POST.get("option_kind")
        form_classes = {
            "building": BuildingForm,
            "status": ProjectStatusForm,
            "category": CategoryForm,
        }
        form_class = form_classes.get(option_kind)
        if not form_class:
            raise Http404("Tipo de opção não encontrado.")
        form = form_class(request.POST, prefix=option_kind)
        forms[option_kind] = form
        if form.is_valid():
            form.save()
            messages.success(request, "Opção cadastrada com sucesso.")
            return redirect("repository:options_list")

    context = {
        "building_form": forms["building"],
        "status_form": forms["status"],
        "category_form": forms["category"],
        "buildings": Building.objects.annotate(project_count=Count("projects", distinct=True)),
        "statuses": ProjectStatus.objects.all(),
        "categories": Category.objects.annotate(project_count=Count("projects", distinct=True)),
    }
    return render(request, "repository/options_list.html", context)


@login_required
def option_edit(request, kind, pk):
    require_team(request.user)
    option_config = {
        "edificacoes": (Building, BuildingForm, "Editar edificação"),
        "status": (ProjectStatus, ProjectStatusForm, "Editar status"),
        "categorias": (Category, CategoryForm, "Editar categoria"),
    }
    config = option_config.get(kind)
    if not config:
        raise Http404("Tipo de opção não encontrado.")
    model, form_class, title = config
    option = get_object_or_404(model, pk=pk)
    form = form_class(request.POST or None, instance=option)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Opção atualizada.")
        return redirect("repository:options_list")
    return render(request, "repository/option_form.html", {"form": form, "title": title})


@login_required
def option_delete(request, kind, pk):
    require_team(request.user)
    option_config = {
        "edificacoes": (Building, "edificação"),
        "status": (ProjectStatus, "status"),
        "categorias": (Category, "categoria"),
    }
    config = option_config.get(kind)
    if not config:
        raise Http404("Tipo de opção não encontrado.")
    model, label = config
    option = get_object_or_404(model, pk=pk)
    if request.method != "POST":
        raise PermissionDenied("Use POST para excluir.")
    name = str(option)
    option.delete()
    messages.success(request, f"{label.capitalize()} excluída: {name}.")
    return redirect("repository:options_list")


@login_required
def person_create(request):
    require_team(request.user)
    form = PersonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pessoa cadastrada.")
        return redirect("repository:people_list")
    return render(request, "repository/person_form.html", {"form": form, "title": "Nova pessoa"})


@login_required
def person_edit(request, pk):
    require_team(request.user)
    person = get_object_or_404(Person, pk=pk)
    form = PersonForm(request.POST or None, instance=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pessoa atualizada.")
        return redirect("repository:people_list")
    return render(request, "repository/person_form.html", {"form": form, "person": person, "title": "Editar pessoa"})


@login_required
def users_list(request):
    require_admin(request.user)
    query = request.GET.get("q", "").strip()
    users = User.objects.select_related("repository_profile").order_by("username")
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    return render(request, "repository/users_list.html", {"users": users, "query": query})


def build_user_activation_token(user):
    return signing.dumps(
        {
            "user_id": user.pk,
            "password": user.password,
            "is_active": user.is_active,
        },
        salt="repository-user-activation",
    )


def send_user_activation_email(request, user):
    token = build_user_activation_token(user)
    activation_url = request.build_absolute_uri(reverse("repository:user_activate", args=[token]))
    body = render_to_string(
        "registration/user_activation_email.txt",
        {
            "user": user,
            "activation_url": activation_url,
            "valid_hours": 1,
        },
    )
    send_mail(
        "Ative seu acesso ao Repositorio de Projetos Arquitetonicos",
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


@login_required
def user_create(request):
    require_admin(request.user)
    form = ManagedUserCreateForm(request.POST or None)
    submit_label = "Enviar convite"
    if request.method == "POST" and form.is_valid():
        user = form.save()
        send_user_activation_email(request, user)
        messages.success(request, "Usuário criado.")
        return redirect("repository:users_list")
    return render(request, "repository/user_form.html", {"form": form, "title": "Novo usuário"})


def user_activate(request, token):
    try:
        data = signing.loads(token, salt="repository-user-activation", max_age=3600)
    except signing.BadSignature:
        return render(request, "registration/user_activate.html", {"validlink": False})

    user = get_object_or_404(User, pk=data.get("user_id"))
    if data.get("password") != user.password or data.get("is_active") != user.is_active:
        return render(request, "registration/user_activate.html", {"validlink": False})

    form = SetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        user.is_active = True
        user.save(update_fields=["is_active"])
        login(request, user)
        messages.success(request, "Cadastro validado e senha definida com sucesso.")
        return redirect("repository:project_list")

    return render(request, "registration/user_activate.html", {"form": form, "validlink": True})


@login_required
def user_detail(request, pk):
    require_admin(request.user)
    managed_user = get_object_or_404(User.objects.select_related("repository_profile", "repository_person"), pk=pk)
    return render(request, "repository/user_detail.html", {"managed_user": managed_user})


@login_required
def user_delete(request, pk):
    require_admin(request.user)
    managed_user = get_object_or_404(User.objects.select_related("repository_profile"), pk=pk)
    if request.method != "POST":
        raise PermissionDenied("Use POST para excluir usuarios.")

    if managed_user.pk == request.user.pk:
        messages.error(request, "Voce nao pode excluir sua propria conta enquanto esta logado.")
        return redirect("repository:users_list")

    if is_admin_user(managed_user):
        active_admins = User.objects.filter(is_active=True, repository_profile__role="admin").exclude(pk=managed_user.pk)
        active_superusers = User.objects.filter(is_active=True, is_superuser=True).exclude(pk=managed_user.pk)
        if not active_admins.exists() and not active_superusers.exists():
            messages.error(request, "Mantenha pelo menos um administrador ativo.")
            return redirect("repository:users_list")

    username = managed_user.get_username()
    managed_user.delete()
    messages.success(request, f"Usuario excluido: {username}.")
    return redirect("repository:users_list")


@login_required
def user_edit(request, pk):
    require_admin(request.user)
    user = get_object_or_404(User, pk=pk)
    form = ManagedUserUpdateForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Usuário atualizado.")
        return redirect("repository:users_list")
    return render(request, "repository/user_form.html", {"form": form, "managed_user": user, "title": "Editar usuário"})
 
