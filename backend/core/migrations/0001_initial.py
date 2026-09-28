from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="LLM",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("OLLAMA", "Ollama"),
                            ("OPENAI", "OpenAI"),
                            ("GEMINI", "Gemini"),
                            ("CUSTOM", "Custom"),
                        ],
                        default="OLLAMA",
                        max_length=20,
                    ),
                ),
                ("base_url", models.URLField(blank=True, null=True)),
                ("model", models.CharField(max_length=100)),
                ("api_key", models.TextField(blank=True, null=True)),
                ("extra", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name="ChatSession",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("title", models.CharField(default="New Session", max_length=200)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "llm",
                    models.ForeignKey(
                        on_delete=models.deletion.PROTECT,
                        related_name="chat_sessions",
                        to="core.llm",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("system", "system"),
                            ("user", "user"),
                            ("assistant", "assistant"),
                            ("tool", "tool"),
                        ],
                        max_length=20,
                    ),
                ),
                ("content", models.TextField()),
                ("name", models.CharField(blank=True, max_length=100, null=True)),
                ("usage", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="messages",
                        to="core.chatsession",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(
                fields=["session", "created_at"], name="core_mess_session_3e15a5_idx"
            ),
        ),
    ]
