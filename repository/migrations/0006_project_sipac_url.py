from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0005_alter_projectfile_description_length"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="sipac_url",
            field=models.URLField(blank=True, verbose_name="link do processo no SIPAC"),
        ),
    ]
