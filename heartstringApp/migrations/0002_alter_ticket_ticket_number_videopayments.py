# Generated by Django 4.2 on 2023-09-11 11:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('heartstringApp', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='ticket_number',
            field=models.CharField(default='77F236EBEB', max_length=10, unique=True),
        ),
        migrations.CreateModel(
            name='VideoPayments',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('ref_number', models.CharField(max_length=255)),
                ('payment_mode', models.CharField(max_length=255)),
                ('msisdn', models.CharField(max_length=255)),
                ('msisdn_idnum', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('added_on', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('video', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='heartstringApp.video')),
            ],
        ),
    ]
