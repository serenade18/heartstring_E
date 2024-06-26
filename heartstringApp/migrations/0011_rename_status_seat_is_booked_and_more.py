# Generated by Django 4.2 on 2024-02-26 12:02

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0010_alter_ticket_ticket_number_alter_ticket_ticket_type_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='seat',
            old_name='status',
            new_name='is_booked',
        ),
        migrations.RenameField(
            model_name='seat',
            old_name='wing',
            new_name='seat_number',
        ),
        migrations.AddField(
            model_name='seat',
            name='play_time',
            field=models.ForeignKey(default=0, on_delete=django.db.models.deletion.CASCADE, to='heartstringApp.playtime'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='seat',
            name='time_slot',
            field=models.CharField(default=0, max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='seat',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='0481200DF3', max_length=10, unique=True),
        ),
        migrations.AlterUniqueTogether(
            name='seat',
            unique_together={('play_time', 'seat_number', 'time_slot')},
        ),
        migrations.RemoveField(
            model_name='seat',
            name='added_on',
        ),
        migrations.RemoveField(
            model_name='seat',
            name='column',
        ),
        migrations.RemoveField(
            model_name='seat',
            name='row',
        ),
        migrations.RemoveField(
            model_name='seat',
            name='seat_id',
        ),
    ]
