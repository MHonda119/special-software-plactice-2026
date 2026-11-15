from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_datasource"),
    ]

    operations = [
        migrations.AlterField(
            model_name="agent",
            name="usecase_type",
            field=models.CharField(
                choices=[
                    ("BASIC_CHAT", "Basic Chat"),
                    ("RAG_CHAT", "RAG Chat"),
                    ("REACT_CHAT", "ReAct Chat"),
                    ("CUSTOM", "Custom"),
                ],
                max_length=20,
            ),
        ),
    ]
