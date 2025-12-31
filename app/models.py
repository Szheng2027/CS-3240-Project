from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
# Create your models here.

class Profile(models.Model):
    YEAR_CHOICES = [
        ('first', 'First Year'),
        ('second', 'Second Year'),
        ('third', 'Third Year'),
        ('fourth', 'Fourth Year'),
        ('grad', 'Graduate Student'),
        ('other', 'Other'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=64, blank=True)
    bags_picked = models.PositiveIntegerField(default=0)
    image = models.ImageField(default='default.jpg', upload_to='profile_pics')
    bio = models.TextField(max_length=500, blank=True, help_text="Short bio about yourself")
    sustainability_interests = models.TextField(max_length=500, blank=True, help_text="Your sustainability interests")
    email_notifications = models.BooleanField(default=False, help_text="Receive email notifications for new messages")
    school_year = models.CharField(max_length=20, choices=YEAR_CHOICES, blank=True, help_text="Your current year at UVA")
    setup_complete = models.BooleanField(default=False, help_text="Whether the user has completed first-time setup")
    
    # In-app notification preferences
    inapp_notifications_enabled = models.BooleanField(default=True, help_text="Enable in-app notifications")
    notify_new_message = models.BooleanField(default=True, help_text="Notify when you receive a new message")
    notify_message_request = models.BooleanField(default=True, help_text="Notify when someone wants to message you")
    notify_group_added = models.BooleanField(default=True, help_text="Notify when added to a group chat")
    banned = models.BooleanField(default=False)
    ban_reason = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.display_name if self.display_name else self.user.username
    
    def get_display_name(self):
        """Return display_name if set, otherwise return Google Account name (first_name last_name), fallback to username"""
        if self.display_name:
            return self.display_name
        if self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        return self.user.username
    
# This signal creates a Profile for a new User
@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

# This signal saves the Profile when the User is saved
@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    instance.profile.save()

class Pickup(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

class Listing(models.Model):
    CATEGORY_CHOICES = [
        ('textbooks', 'Textbooks'),
        ('furniture', 'Furniture'),
        ('electronics', 'Electronics'),
        ('clothing', 'Clothing'),
        ('supplies', 'School Supplies'),
        ('other', 'Other'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    TAG_CHOICES = [
        ('dorm', 'Dorm Essentials'),
        ('academic', 'Academic'),
        ('tech', 'Tech'),
        ('fashion', 'Fashion'),
        ('sports', 'Sports/Outdoor'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=500, blank=True, help_text="Describe your item")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='listing_pics', null=True, blank=True)
    views = models.PositiveIntegerField(default=0, help_text="Number of times this listing has been viewed")
    tags = models.TextField(blank=True, help_text="Comma-separated topic tags for discoverability")

    def get_tags_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
    
    def set_tags_from_list(self, tags_list):
        if not tags_list:
            self.tags = ""
        else:
            # join with commas and remove empty items
            cleaned = [tag.strip() for tag in tags_list if tag.strip()]
            self.tags = ", ".join(cleaned)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.owner.username})"

class ContentFlag(models.Model):
    REASON_CHOICES = [
        ('spam', 'Spam'),
        ('inappropriate', 'Inappropriate Content'),
        ('harassment', 'Harassment'),
        ('scam', 'Scam/Fraud'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ]
    
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='flags', null=True, blank=True)
    flagged_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flags_created')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True, help_text="Additional details about the flag")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='flags_reviewed')
    admin_notes = models.TextField(blank=True, help_text="Admin notes about resolution")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Flag on Listing {self.listing.id} by {self.flagged_by.username}"

class BanAppeal(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="ban_appeals")
    subject = models.CharField(max_length=200)
    message = models.TextField()
    evidence = models.FileField(upload_to="appeal_evidence/", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        try:
            display = self.user.get_full_name() or self.user.username
        except Exception:
            display = self.user.username
        return f"Appeal by {display} ({self.status})"

