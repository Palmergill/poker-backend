# Generated by Django 4.2.7 on 2025-06-23 12:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poker_api', '0005_game_hand_count_handhistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='winner_info',
            field=models.TextField(blank=True, null=True),
        ),
    ]
