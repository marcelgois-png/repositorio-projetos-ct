from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import Building, Category, Person, Project, ProjectFile, ProjectImage, ProjectMember, ProjectStatus, UserProfile
from .permissions import ROLE_ADMIN, ROLE_READER, ROLE_TEAM


User = get_user_model()


def project_status_choices(include_code=None):
    statuses = ProjectStatus.objects.filter(is_active=True)
    if include_code:
        statuses = statuses | ProjectStatus.objects.filter(code=include_code)
    choices = [(status.code, status.name) for status in statuses.distinct().order_by("name")]
    return choices or list(Project.Status.choices)


class BootstrapFormMixin:
    check_widget_classes = (forms.CheckboxInput, forms.CheckboxSelectMultiple, forms.RadioSelect)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, self.check_widget_classes):
                continue
            current_class = widget.attrs.get("class", "")
            if isinstance(widget, forms.SelectMultiple):
                css_class = "form-select tomselect"
            elif isinstance(widget, forms.Select):
                css_class = "form-select"
            elif isinstance(widget, forms.ClearableFileInput):
                css_class = "form-control"
            else:
                css_class = "form-control"
            widget.attrs["class"] = f"{current_class} {css_class}".strip()
        for field in self.fields.values():
            if field.required:
                field.label = f"{field.label} *"


class ProjectFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(label="Busca", required=False)
    category_discipline = forms.MultipleChoiceField(
        label="Tipo de projeto",
        required=False,
        choices=(),
        widget=forms.SelectMultiple(
            attrs={
                "data-placeholder": "Selecione tipos",
            }
        ),
    )
    status = forms.ChoiceField(label="Status", choices=(), required=False)
    building = forms.ModelChoiceField(
        label="Edificação",
        queryset=Building.objects.filter(is_active=True),
        required=False,
        empty_label="Todas",
    )
    requested_by = forms.CharField(label="Demandante do projeto", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [("", "Todos")] + project_status_choices()
        category_choices = [(f"cat:{category.pk}", category.name) for category in Category.objects.filter(is_active=True)]
        discipline_choices = [(f"disc:{value}", label) for value, label in ProjectFile.Discipline.choices]
        self.fields["category_discipline"].choices = [
            ("Categorias", category_choices),
            ("Disciplinas", discipline_choices),
        ]
        self.fields["q"].widget.attrs["placeholder"] = "Nome, local, equipe ou arquivo"
        self.fields["requested_by"].widget.attrs["placeholder"] = "Nome do demandante"


class UsernameReminderForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(
        label="E-mail cadastrado",
        widget=forms.EmailInput(attrs={"placeholder": "seu.email@ufpb.br", "autocomplete": "email"}),
    )


class ProjectForm(BootstrapFormMixin, forms.ModelForm):
    status = forms.ChoiceField(label="Status", choices=())

    class Meta:
        model = Project
        fields = [
            "name",
            "description",
            "cover_image",
            "building",
            "requested_by",
            "sipac_url",
            "start_date",
            "end_date",
            "status",
            "visibility",
            "categories",
            "notes",
        ]
        labels = {
            "building": "Edificação",
            "requested_by": "Demandante do projeto",
            "sipac_url": "Link do processo no SIPAC",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 5}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "status": forms.Select(attrs={"data-project-status": "true"}),
            "end_date": forms.DateInput(attrs={"type": "date", "data-project-end-date": "true"}, format="%Y-%m-%d"),
            "visibility": forms.RadioSelect(),
            "categories": forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_building_pk = getattr(self.instance, "building_id", None)
        building_queryset = Building.objects.filter(is_active=True)
        if current_building_pk:
            building_queryset = building_queryset | Building.objects.filter(pk=current_building_pk)
        self.fields["building"].queryset = building_queryset.distinct().order_by("name")
        self.fields["building"].empty_label = "Selecione a edificação"

        current_status = getattr(self.instance, "status", None)
        self.fields["status"].choices = project_status_choices(current_status)
        self.fields["status"].widget.attrs["data-project-status"] = "true"
        self.fields["sipac_url"].widget.attrs["placeholder"] = "https://sipac.ufpb.br/..."

        if self.instance.pk:
            self.fields["categories"].queryset = Category.objects.filter(Q(is_active=True) | Q(projects=self.instance)).distinct()
        else:
            self.fields["categories"].queryset = Category.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        end_date = cleaned_data.get("end_date")
        saved_status = ProjectStatus.objects.filter(code=status).first()
        requires_end_date = saved_status.requires_end_date if saved_status else status in {Project.Status.COMPLETED, Project.Status.ARCHIVED}
        if requires_end_date and not end_date:
            self.add_error("end_date", "Informe a data de conclusão para projetos concluídos ou arquivados.")
        return cleaned_data

    def save(self, commit=True):
        project = super().save(commit=False)
        if project.building_id:
            project.location = project.building.name
        else:
            project.location = ""
        if commit:
            project.save()
            self.save_m2m()
        return project


class BuildingForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Building
        fields = ["name", "description", "is_active"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}


class ProjectStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectStatus
        fields = ["name", "code", "requires_end_date", "is_active"]
        help_texts = {
            "code": "Opcional. Se ficar em branco, o sistema cria um código a partir do nome.",
            "requires_end_date": "Marque quando este status exigir data de conclusão.",
        }


class CategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "color", "is_active"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "color": forms.TextInput(attrs={"type": "color"}),
        }


class PersonForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Person
        fields = ["name", "function", "institutional_link", "email", "phone", "user", "is_active", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = User.objects.filter(repository_person__isnull=True)
        if self.instance.pk and self.instance.user_id:
            queryset = queryset | User.objects.filter(pk=self.instance.user_id)
        self.fields["user"].queryset = queryset.order_by("username")


class ProjectMemberForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectMember
        fields = ["person", "role", "responsibility"]


class ProjectFileForm(BootstrapFormMixin, forms.ModelForm):
    description = forms.CharField(
        label="Descrição",
        required=False,
        max_length=140,
        widget=forms.Textarea(attrs={"rows": 2, "maxlength": 140}),
    )

    class Meta:
        model = ProjectFile
        fields = ["title", "file", "file_type", "version", "responsible", "description"]
        help_texts = {"description": "Máximo de 140 caracteres."}


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Usuario ou e-mail",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    def clean(self):
        login = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if login is not None and password:
            username = login
            if "@" in login:
                matched_user = User.objects.filter(email__iexact=login).order_by("pk").first()
                if matched_user:
                    username = matched_user.get_username()

            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ManagedUserCreateForm(BootstrapFormMixin, forms.ModelForm):
    role = forms.ChoiceField(
        label="Perfil",
        choices=[
            (ROLE_READER, "Leitor"),
            (ROLE_TEAM, "Equipe"),
            (ROLE_ADMIN, "Admin"),
        ],
    )
    person = forms.ModelChoiceField(
        label="Pessoa vinculada",
        queryset=Person.objects.filter(user__isnull=True),
        required=False,
        empty_label="Sem vínculo",
    )
    email = forms.EmailField(label="E-mail")
    first_name = forms.CharField(label="Nome")
    last_name = forms.CharField(label="Sobrenome")

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "role", "person")

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Este e-mail ja esta cadastrado.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.is_active = False
        user.set_unusable_password()
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = self.cleaned_data["role"]
            profile.save()
            person = self.cleaned_data.get("person")
            if person:
                person.user = user
                person.save(update_fields=["user", "updated_at"])
        return user


class ManagedUserUpdateForm(BootstrapFormMixin, forms.ModelForm):
    role = forms.ChoiceField(
        label="Perfil",
        choices=[
            (ROLE_READER, "Leitor"),
            (ROLE_TEAM, "Equipe"),
            (ROLE_ADMIN, "Admin"),
        ],
    )
    person = forms.ModelChoiceField(label="Pessoa vinculada", queryset=Person.objects.none(), required=False)

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active", "role", "person"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=self.instance)
        self.fields["role"].initial = profile.role
        self.fields["person"].queryset = Person.objects.filter(user__isnull=True) | Person.objects.filter(user=self.instance)
        current_person = getattr(self.instance, "repository_person", None)
        if current_person:
            self.fields["person"].initial = current_person

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("role") == ROLE_ADMIN and not cleaned_data.get("is_active", True):
            active_admins = User.objects.filter(
                is_active=True,
                repository_profile__role=ROLE_ADMIN,
            ).exclude(pk=self.instance.pk)
            if not active_admins.exists() and not User.objects.filter(is_active=True, is_superuser=True).exclude(pk=self.instance.pk).exists():
                raise ValidationError("Mantenha pelo menos um administrador ativo.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = self.cleaned_data["role"]
        if commit:
            profile.save()
            Person.objects.filter(user=user).exclude(pk=getattr(self.cleaned_data.get("person"), "pk", None)).update(user=None)
            person = self.cleaned_data.get("person")
            if person:
                person.user = user
                person.save(update_fields=["user", "updated_at"])
        return user


class ProjectImageForm(forms.ModelForm):
    class Meta:
        model = ProjectImage
        fields = ["image", "caption"]
        labels = {
            "image": "Imagem",
            "caption": "Legenda (opcional)",
        }
        widgets = {
            "caption": forms.TextInput(attrs={"placeholder": "Ex: Vista frontal, Renderização interna…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs["class"] = "form-control"
        self.fields["caption"].widget.attrs["class"] = "form-control"
