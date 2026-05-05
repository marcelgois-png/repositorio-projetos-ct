from django.db import migrations
from django.utils.text import slugify


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


def unique_building_slug(Building, name):
    base_slug = slugify(name) or "edificacao"
    slug = base_slug
    counter = 2
    while Building.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def seed_buildings(apps, schema_editor):
    Building = apps.get_model("repository", "Building")
    for name in INITIAL_BUILDINGS:
        Building.objects.get_or_create(
            name=name,
            defaults={"slug": unique_building_slug(Building, name), "is_active": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("repository", "0003_building_projectstatus_project_building_and_status"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="building",
            options={"ordering": ["name"], "verbose_name": "edificação", "verbose_name_plural": "edificações"},
        ),
        migrations.AlterModelOptions(
            name="projectstatus",
            options={"ordering": ["name"], "verbose_name": "status de projeto", "verbose_name_plural": "status de projeto"},
        ),
        migrations.RemoveField(
            model_name="building",
            name="sort_order",
        ),
        migrations.RemoveField(
            model_name="projectstatus",
            name="sort_order",
        ),
        migrations.RunPython(seed_buildings, migrations.RunPython.noop),
    ]
