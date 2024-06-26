# Generated by Django 4.2 on 2024-02-26 13:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0011_rename_status_seat_is_booked_and_more'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='seat',
            name='wing',
            field=models.CharField(default=0, max_length=50),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='4241756324', max_length=10, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together={('play_time', 'seat_number', 'wing', 'time_slot')},
        ),
    ]
