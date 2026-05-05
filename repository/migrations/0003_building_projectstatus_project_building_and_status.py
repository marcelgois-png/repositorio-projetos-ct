from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def unique_building_slug(Building, name):
    base_slug = slugify(name) or "edificacao"
    slug = base_slug
    counter = 2
    while Building.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def migrate_existing_buildings(apps, schema_editor):
    Building = apps.get_model("repository", "Building")
    Project = apps.get_model("repository", "Project")
    for location in Project.objects.exclude(location="").values_list("location", flat=True).distinct():
        building, _ = Building.objects.get_or_create(
            name=location,
            defaults={"slug": unique_building_slug(Building, location)},
        )
        Project.objects.filter(location=location, building__isnull=True).update(building=building)


def seed_project_statuses(apps, schema_editor):
    ProjectStatus = apps.get_model("repository", "ProjectStatus")
    statuses = [
        ("draft", "Rascunho", False, 10),
        ("in_progress", "Em andamento", False, 20),
        ("completed", "Concluído", True, 30),
        ("archived", "Arquivado", True, 40),
    ]
    for code, name, requires_end_date, sort_order in statuses:
        ProjectStatus.objects.get_or_create(
            code=code,
            defaults={
                "name": name,
                "requires_end_date": requires_end_date,
                "sort_order": sort_order,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0002_alter_category_color"),
    ]

    operations = [
        migrations.CreateModel(
            name="Building",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, unique=True, verbose_name="nome")),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True, verbose_name="slug")),
                ("description", models.TextField(blank=True, verbose_name="descrição")),
                ("is_active", models.BooleanField(default=True, verbose_name="ativa")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="ordem")),
            ],
            options={
                "verbose_name": "edificação",
                "verbose_name_plural": "edificações",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="ProjectStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.SlugField(blank=True, max_length=40, unique=True, verbose_name="código")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="nome")),
                ("requires_end_date", models.BooleanField(default=False, verbose_name="exige data de conclusão")),
                ("is_active", models.BooleanField(default=True, verbose_name="ativo")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="ordem")),
            ],
            options={
                "verbose_name": "status de projeto",
                "verbose_name_plural": "status de projeto",
                "ordering": ["sort_order", "name"],
            },
        ),
        migrations.AddField(
            model_name="project",
            name="building",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="projects",
                to="repository.building",
                verbose_name="edificação",
            ),
        ),
        migrations.AlterField(
            model_name="project",
            name="status",
            field=models.CharField(default="in_progress", max_length=40, verbose_name="status"),
        ),
        migrations.RunPython(seed_project_statuses, migrations.RunPython.noop),
        migrations.RunPython(migrate_existing_buildings, migrations.RunPython.noop),
    ]
