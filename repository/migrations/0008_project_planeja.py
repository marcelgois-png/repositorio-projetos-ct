from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0007_projectimage"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="planeja_name",
            field=models.CharField(blank=True, max_length=220, verbose_name="nome do projeto no Planeja"),
        ),
        migrations.AddField(
            model_name="project",
            name="planeja_url",
            field=models.URLField(blank=True, verbose_name="link do projeto no Planeja"),
        ),
    ]
