from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="color",
            field=models.CharField(default="#283E4C", max_length=7, verbose_name="cor"),
        ),
    ]
