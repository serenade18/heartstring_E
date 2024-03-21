# Generated by Django 4.2 on 2024-02-28 14:20

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0012_alter_seat_unique_together_seat_wing_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='seat',
            name='play_date',
            field=models.DateField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='A3D8EFD882', max_length=10, unique=True),
        ),
    ]
