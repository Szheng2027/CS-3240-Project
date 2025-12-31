from django.db import models
from django.contrib.auth.models import User


class Notification(models.Model):
    """Model for in-app notifications."""
    
    NOTIFICATION_TYPES = [
        ('new_message', 'New Message'),
        ('message_request', 'Message Request'),
        ('group_added', 'Added to Group Chat'),
        ('general', 'General'),
    ]
    
    recipient = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20, 
        choices=NOTIFICATION_TYPES, 
        default='general'
    )
    title = models.CharField(max_length=100)
    message = models.TextField(max_length=500)
    link = models.CharField(max_length=200, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Optional: reference to related objects
    sender = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sent_notifications'
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.notification_type}: {self.title} -> {self.recipient.username}"
    
    @classmethod
    def create_notification(cls, recipient, notification_type, title, message, link=None, sender=None):
        """
        Helper method to create a notification if the user has that notification type enabled.
        Returns the notification if created, None otherwise.
        """
        # Check if user has in-app notifications enabled for this type
        try:
            profile = recipient.profile
            if not profile.inapp_notifications_enabled:
                return None
            
            # Check specific notification type preferences
            type_preferences = {
                'new_message': profile.notify_new_message,
                'message_request': profile.notify_message_request,
                'group_added': profile.notify_group_added,
                'general': True,  # General notifications always allowed if main toggle is on
            }
            
            if not type_preferences.get(notification_type, True):
                return None
                
        except Exception:
            # If profile doesn't exist or error, don't create notification
            return None
        
        return cls.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            sender=sender
        )
