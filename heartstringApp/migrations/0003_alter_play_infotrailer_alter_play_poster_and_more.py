# Generated by Django 4.2 on 2023-12-15 10:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0002_useraccount_added_on_alter_ticket_ticket_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='play',
            name='infotrailer',
            field=models.FileField(blank=True, null=True, upload_to='info-trailers/'),
        ),
        migrations.AlterField(
            model_name='play',
            name='poster',
            field=models.ImageField(blank=True, null=True, upload_to='posters/'),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='DAB777292A', max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name='video',
            name='trailer',
            field=models.FileField(blank=True, null=True, upload_to='trailers/'),
        ),
        migrations.AlterField(
            model_name='video',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to='videos/'),
        ),
        migrations.AlterField(
            model_name='video',
            name='video_poster',
            field=models.ImageField(blank=True, null=True, upload_to='video_poster/'),
        ),
    ]
