from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("repository", "0004_remove_option_sort_order_and_seed_buildings"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectfile",
            name="description",
            field=models.TextField(blank=True, max_length=140, verbose_name="descrição"),
        ),
    ]
