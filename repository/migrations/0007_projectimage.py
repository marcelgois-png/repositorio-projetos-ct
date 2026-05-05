from django.db import migrations, models
import django.core.validators
import repository.models


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0006_project_sipac_url"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProjectImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(
                    upload_to=repository.models.project_image_upload_path,
                    validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
                    verbose_name="imagem",
                )),
                ("caption", models.CharField(blank=True, max_length=220, verbose_name="legenda")),
                ("order", models.PositiveIntegerField(default=0, verbose_name="ordem")),
                ("uploaded_at", models.DateTimeField(auto_now_add=True, verbose_name="enviado em")),
                ("project", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="images",
                    to="repository.project",
                    verbose_name="projeto",
                )),
            ],
            options={
                "verbose_name": "imagem do projeto",
                "verbose_name_plural": "imagens do projeto",
                "ordering": ["order", "uploaded_at"],
            },
        ),
    ]
