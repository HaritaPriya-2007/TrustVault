from django.db import migrations, models

import documents.models
import documents.storage


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0002_alter_document_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="document",
            name="file",
            field=models.FileField(
                storage=documents.storage.vault_document_storage,
                upload_to=documents.models.vault_blob_name,
            ),
        ),
        migrations.AlterField(
            model_name="document",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(fields=["title"], name="documents_d_title_idx"),
        ),
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["original_filename"],
                name="documents_d_origfile_idx",
            ),
        ),
    ]
