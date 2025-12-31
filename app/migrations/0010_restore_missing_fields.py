from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('app', '0009_listing_tags_profile_ban_reason_profile_banned_and_more'),
    ]

    operations = [
        # Missing Profile fields
        migrations.AddField(
            model_name='profile',
            name='inapp_notifications_enabled',
            field=models.BooleanField(default=True, help_text='Enable in-app notifications'),
        ),
        migrations.AddField(
            model_name='profile',
            name='notify_new_message',
            field=models.BooleanField(default=True, help_text='Notify when you receive a new message'),
        ),
        migrations.AddField(
            model_name='profile',
            name='notify_message_request',
            field=models.BooleanField(default=True, help_text='Notify when someone wants to message you'),
        ),
        migrations.AddField(
            model_name='profile',
            name='notify_group_added',
            field=models.BooleanField(default=True, help_text='Notify when added to a group chat'),
        ),
        migrations.AddField(
            model_name='profile',
            name='banned',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='ban_reason',
            field=models.CharField(max_length=100, blank=True),
        ),

        # Missing Listing field
        migrations.AddField(
            model_name='listing',
            name='tags',
            field=models.TextField(blank=True, help_text='Comma-separated topic tags for discoverability'),
        ),
    ]
