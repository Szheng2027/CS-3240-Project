from django.contrib import admin
from .models import Profile, Pickup, Listing, ContentFlag
from django.utils import timezone
# Register your models here.

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name")

@admin.register(Pickup)
class PickupAdmin(admin.ModelAdmin):
    list_display = ("user", "count", "created_at")

@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_active", "created_at", "flag_count")
    list_filter = ("is_active",)
    search_fields = ("title", "owner__username")
    
    def flag_count(self, obj):
        return obj.flags.filter(status='pending').count()
    flag_count.short_description = 'Pending Flags'

@admin.register(ContentFlag)
class ContentFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "listing_link", "reason", "flagged_by", "status", "created_at")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("listing__title", "flagged_by__username", "description")
    readonly_fields = ("created_at", "flagged_by")
    actions = ['mark_reviewed', 'mark_resolved', 'mark_dismissed']
    
    fieldsets = (
        ('Flag Information', {
            'fields': ('listing', 'flagged_by', 'reason', 'description', 'created_at')
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'admin_notes')
        }),
    )
    
    def listing_link(self, obj):
        if obj.listing:
            return f"Listing #{obj.listing.id}: {obj.listing.title}"
        return "N/A"
    listing_link.short_description = 'Flagged Content'
    
    def mark_reviewed(self, request, queryset):
        queryset.update(status='reviewed', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} flags marked as reviewed.")
    mark_reviewed.short_description = "Mark selected flags as reviewed"
    
    def mark_resolved(self, request, queryset):
        queryset.update(status='resolved', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} flags marked as resolved.")
    mark_resolved.short_description = "Mark selected flags as resolved"
    
    def mark_dismissed(self, request, queryset):
        queryset.update(status='dismissed', reviewed_by=request.user, reviewed_at=timezone.now())
        self.message_user(request, f"{queryset.count()} flags dismissed.")
    mark_dismissed.short_description = "Dismiss selected flags"