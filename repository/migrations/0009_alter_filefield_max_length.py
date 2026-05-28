from django.db import migrations, models
import django.core.validators
import repository.models


class Migration(migrations.Migration):
    dependencies = [
        ("repository", "0008_project_planeja"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="cover_image",
            field=models.ImageField(
                blank=True,
                max_length=200,
                upload_to=repository.models.project_cover_upload_path,
                validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
                verbose_name="imagem de capa",
            ),
        ),
        migrations.AlterField(
            model_name="projectfile",
            name="file",
            field=models.FileField(
                max_length=200,
                storage=repository.models.PrivateMediaStorage(),
                upload_to=repository.models.project_file_upload_path,
                validators=[
                    repository.models.validate_project_file_extension,
                    repository.models.validate_upload_size,
                ],
                verbose_name="arquivo",
            ),
        ),
        migrations.AlterField(
            model_name="projectimage",
            name="image",
            field=models.ImageField(
                max_length=200,
                upload_to=repository.models.project_image_upload_path,
                validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "webp"])],
                verbose_name="imagem",
            ),
        ),
    ]
