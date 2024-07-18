# Generated by Django 4.2.11 on 2024-07-16 13:07

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('mathesar', '0010_alter_tablemetadata_column_order_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Explorations',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=128, unique=True)),
                ('base_table_oid', models.PositiveBigIntegerField()),
                ('initial_columns', models.JSONField()),
                ('transformations', models.JSONField(null=True)),
                ('display_options', models.JSONField(null=True)),
                ('display_names', models.JSONField()),
                ('description', models.CharField(null=True)),
                ('database', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='mathesar.database')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]