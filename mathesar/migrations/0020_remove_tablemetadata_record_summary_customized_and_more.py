# Generated by Django 4.2.11 on 2024-10-23 14:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mathesar', '0019_clear_record_summary_template_values'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='tablemetadata',
            name='record_summary_customized',
        ),
        migrations.AlterField(
            model_name='tablemetadata',
            name='record_summary_template',
            field=models.JSONField(null=True),
        ),
    ]