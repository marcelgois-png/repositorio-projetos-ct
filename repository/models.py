import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.validators import FileExtensionValidator
from django.db import models
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property
from django.utils.text import slugify

from .permissions import ROLE_ADMIN, ROLE_READER, ROLE_TEAM


User = get_user_model()


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)


private_storage = PrivateMediaStorage()

ALLOWED_PROJECT_FILE_EXTENSIONS = {
    "dwg",
    "dxf",
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "webp",
    "skp",
    "rvt",
    "ifc",
    "3dm",
    "obj",
    "fbx",
    "xlsx",
    "xls",
    "ods",
    "doc",
    "docx",
    "txt",
    "zip",
    "rar",
    "7z",
}


def validate_project_file_extension(value):
    extension = Path(value.name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_PROJECT_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_PROJECT_FILE_EXTENSIONS))
        raise ValidationError(f"Extensão .{extension or 'sem extensão'} não permitida. Use: {allowed}.")


def validate_upload_size(value):
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if value.size > max_bytes:
        raise ValidationError(f"O arquivo excede o limite de {settings.MAX_UPLOAD_MB} MB.")


def project_cover_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    slug = instance.slug or slugify(instance.name) or "projeto"
    return f"project_covers/{slug}/{uuid.uuid4().hex}{extension}"


def project_file_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    project_slug = instance.project.slug or slugify(instance.project.name) or "projeto"
    return f"project_files/{project_slug}/{uuid.uuid4().hex}{extension}"


class UserProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = ROLE_ADMIN, "Admin"
        TEAM = ROLE_TEAM, "Equipe"
        READER = ROLE_READER, "Leitor"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="repository_profile",
        verbose_name="usuário",
    )
    role = models.CharField("perfil", max_length=20, choices=Role.choices, default=Role.READER)

    class Meta:
        verbose_name = "perfil de usuário"
        verbose_name_plural = "perfis de usuário"

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"


class Person(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repository_person",
        verbose_name="usuário vinculado",
    )
    name = models.CharField("nome", max_length=180)
    function = models.CharField("função", max_length=140, blank=True)
    institutional_link = models.CharField("vínculo institucional", max_length=180, blank=True)
    email = models.EmailField("e-mail", blank=True)
    phone = models.CharField("telefone", max_length=40, blank=True)
    is_active = models.BooleanField("ativo", default=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "pessoa"
        verbose_name_plural = "pessoas"

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField("nome", max_length=120, unique=True)
    slug = models.SlugField("slug", max_length=140, unique=True, blank=True)
    description = models.TextField("descrição", blank=True)
    color = models.CharField("cor", max_length=7, default="#283E4C")
    is_active = models.BooleanField("ativa", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "categoria"
        verbose_name_plural = "categorias"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Building(models.Model):
    name = models.CharField("nome", max_length=180, unique=True)
    slug = models.SlugField("slug", max_length=200, unique=True, blank=True)
    description = models.TextField("descrição", blank=True)
    is_active = models.BooleanField("ativa", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "edificação"
        verbose_name_plural = "edificações"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProjectStatus(models.Model):
    code = models.SlugField("código", max_length=40, unique=True, blank=True)
    name = models.CharField("nome", max_length=80, unique=True)
    requires_end_date = models.BooleanField("exige data de conclusão", default=False)
    is_active = models.BooleanField("ativo", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "status de projeto"
        verbose_name_plural = "status de projeto"

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Project(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Rascunho"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluído"
        ARCHIVED = "archived", "Arquivado"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Catálogo público"
        RESTRICTED = "restricted", "Restrito"

    name = models.CharField("nome", max_length=220)
    slug = models.SlugField("slug", max_length=240, unique=True, blank=True)
    description = models.TextField("descrição")
    cover_image = models.ImageField(
        "imagem de capa",
        upload_to=project_cover_upload_path,
        blank=True,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
        verbose_name="edificação",
    )
    location = models.CharField("localização/unidade", max_length=220, blank=True)
    requested_by = models.CharField("demandante", max_length=220, blank=True)
    sipac_url = models.URLField("link do processo no SIPAC", blank=True)
    planeja_name = models.CharField("nome do projeto no Planeja", max_length=220, blank=True)
    planeja_url = models.URLField("link do projeto no Planeja", blank=True)
    start_date = models.DateField("data de início", null=True, blank=True)
    end_date = models.DateField("data de conclusão", null=True, blank=True)
    status = models.CharField("status", max_length=40, default=Status.IN_PROGRESS)
    visibility = models.CharField(
        "visibilidade",
        max_length=30,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    categories = models.ManyToManyField(Category, blank=True, related_name="projects", verbose_name="categorias")
    team = models.ManyToManyField(
        Person,
        through="ProjectMember",
        blank=True,
        related_name="projects",
        verbose_name="equipe",
    )
    notes = models.TextField("observações internas", blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_projects",
        verbose_name="criado por",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_projects",
        verbose_name="atualizado por",
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "name"]
        verbose_name = "projeto"
        verbose_name_plural = "projetos"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("repository:project_detail", kwargs={"slug": self.slug})

    @property
    def year_range(self):
        start_year = self.start_date.year if self.start_date else None
        end_year = self.end_date.year if self.end_date else None
        if start_year and end_year and start_year != end_year:
            return f"{start_year} - {end_year}"
        if start_year:
            return str(start_year)
        if end_year:
            return str(end_year)
        return ""

    @property
    def building_name(self):
        if self.building_id:
            return self.building.name
        return self.location

    @property
    def status_label(self):
        status = ProjectStatus.objects.filter(code=self.status).first()
        if status:
            return status.name
        return dict(self.Status.choices).get(self.status, self.status)

    @property
    def allows_public_download(self):
        if self.visibility != self.Visibility.PUBLIC:
            return False
        status = ProjectStatus.objects.filter(code=self.status).first()
        if status:
            return status.requires_end_date
        return self.status in {self.Status.COMPLETED, self.Status.ARCHIVED}

    def __str__(self):
        return self.name


class ProjectMember(models.Model):
    class Role(models.TextChoices):
        COORDINATION = "coordination", "Coordenação"
        ARCHITECTURE = "architecture", "Arquitetura"
        ENGINEERING = "engineering", "Engenharia"
        INTERN = "intern", "Estágio/Bolsista"
        COLLABORATOR = "collaborator", "Colaboração"
        OTHER = "other", "Outro"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships", verbose_name="projeto")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="memberships", verbose_name="pessoa")
    role = models.CharField("papel", max_length=40, choices=Role.choices, default=Role.COLLABORATOR)
    responsibility = models.CharField("responsabilidade", max_length=180, blank=True)
    order = models.PositiveSmallIntegerField("ordem", default=0)

    class Meta:
        ordering = ["order", "person__name"]
        unique_together = [("project", "person", "role")]
        verbose_name = "integrante do projeto"
        verbose_name_plural = "integrantes do projeto"

    def __str__(self):
        return f"{self.person} - {self.project}"


class ProjectFile(models.Model):
    class FileType(models.TextChoices):
        DWG = "dwg", "DWG/AutoCAD"
        DXF = "dxf", "DXF"
        PDF = "pdf", "PDF"
        IMAGE = "image", "Imagem/render"
        MODEL_3D = "model_3d", "Modelo 3D"
        SPREADSHEET = "spreadsheet", "Planilha"
        MEMORIAL = "memorial", "Memorial/descritivo"
        OTHER = "other", "Outro"

    class Discipline(models.TextChoices):
        ARCHITECTURE = "architecture", "Arquitetônico"
        ELECTRICAL = "electrical", "Elétrico"
        HYDRAULIC = "hydraulic", "Hidrossanitário"
        LOGIC = "logic", "Lógica/rede"
        LANDSCAPE = "landscape", "Paisagismo"
        URBANISM = "urbanism", "Urbanismo"
        ACCESSIBILITY = "accessibility", "Acessibilidade"
        HVAC = "hvac", "Climatização"
        FIRE = "fire", "Prevenção e combate a incêndio"
        SIGNAGE = "signage", "Comunicação visual/sinalização"
        COMPATIBILITY = "compatibility", "Compatibilização"
        OTHER = "other", "Outro"

    class Status(models.TextChoices):
        CURRENT = "current", "Atual"
        SUPERSEDED = "superseded", "Substituído"
        DRAFT = "draft", "Rascunho"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files", verbose_name="projeto")
    title = models.CharField("título", max_length=180)
    file = models.FileField(
        "arquivo",
        upload_to=project_file_upload_path,
        storage=private_storage,
        validators=[validate_project_file_extension, validate_upload_size],
    )
    file_type = models.CharField("tipo", max_length=40, choices=FileType.choices)
    discipline = models.CharField("disciplina", max_length=40, choices=Discipline.choices, default=Discipline.ARCHITECTURE)
    version = models.CharField("versão", max_length=40, default="v1")
    responsible = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_files",
        verbose_name="responsável técnico",
    )
    description = models.TextField("descrição", blank=True, max_length=140)
    status = models.CharField("status", max_length=40, choices=Status.choices, default=Status.CURRENT)
    original_filename = models.CharField("nome original", max_length=255, blank=True)
    size = models.PositiveBigIntegerField("tamanho em bytes", default=0)
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_project_files",
        verbose_name="enviado por",
    )
    uploaded_at = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "title"]
        indexes = [
            models.Index(fields=["project", "file_type"]),
            models.Index(fields=["project", "discipline"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "arquivo do projeto"
        verbose_name_plural = "arquivos do projeto"

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = Path(self.file.name).name
        if self.file:
            self.size = getattr(self.file, "size", self.size) or self.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.version})"

    @property
    def extension(self):
        return Path(self.original_filename or self.file.name).suffix.lower().lstrip(".")

    @property
    def display_filename(self):
        if self.original_filename:
            return self.original_filename
        if self.file:
            return Path(self.file.name).name
        return "Arquivo sem nome"

    @property
    def size_mb(self):
        if not self.size:
            return "0 MB"
        return f"{self.size / (1024 * 1024):.1f} MB"


def project_image_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    project_slug = instance.project.slug or slugify(instance.project.name) or "projeto"
    return f"project_images/{project_slug}/{uuid.uuid4().hex}{extension}"


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="images", verbose_name="projeto")
    image = models.ImageField(
        "imagem",
        upload_to=project_image_upload_path,
        validators=[FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
    )
    caption = models.CharField("legenda", max_length=220, blank=True)
    order = models.PositiveIntegerField("ordem", default=0)
    uploaded_at = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        ordering = ["order", "uploaded_at"]
        verbose_name = "imagem do projeto"
        verbose_name_plural = "imagens do projeto"

    def __str__(self):
        return f"Imagem {self.pk} — {self.project.name}"


def unique_slug(instance, value):
    base_slug = slugify(value) or "item"
    slug = base_slug
    counter = 2
    model = instance.__class__
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug
