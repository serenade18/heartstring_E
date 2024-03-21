# Generated by Django 4.2 on 2023-12-18 18:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0003_alter_play_infotrailer_alter_play_poster_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='duration',
            field=models.CharField(default=0, max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='0AED0970B0', max_length=10, unique=True),
        ),
    ]
