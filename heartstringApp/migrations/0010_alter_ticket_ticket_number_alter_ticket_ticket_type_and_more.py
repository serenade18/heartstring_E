# Generated by Django 4.2 on 2024-02-24 01:34

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0009_alter_play_location_alter_ticket_ticket_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='D8F4DCFBBB', max_length=10, unique=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_type',
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.DeleteModel(
            name='Bogof',
        ),
    ]
