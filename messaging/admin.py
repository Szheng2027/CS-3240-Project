from django.contrib import admin
from .models import Thread, Message, MessageFlag
from django.utils import timezone

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'body', 'created_at')

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    inlines = [MessageInline]
    list_display = ('id', 'participants_list', 'created_at')
    search_fields = ('participants__username',)
    filter_horizontal = ('participants',)

    def participants_list(self, obj):
        return ", ".join([u.username for u in obj.participants.all()])
    participants_list.short_description = 'Participants'

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'created_at', 'body_short', 'flag_count')
    list_filter = ('created_at', 'sender')
    search_fields = ('body', 'sender__username')
    readonly_fields = ('created_at',)

    def body_short(self, obj):
        return obj.body[:60] + ('...' if len(obj.body) > 60 else '')
    body_short.short_description = 'Body'
    
    def flag_count(self, obj):
        return obj.flags.filter(status='pending').count()
    flag_count.short_description = 'Pending Flags'

@admin.register(MessageFlag)
class MessageFlagAdmin(admin.ModelAdmin):
    list_display = ("id", "message_preview", "reason", "flagged_by", "status", "created_at")
    list_filter = ("status", "reason", "created_at")
    search_fields = ("message__body", "flagged_by__username", "description")
    readonly_fields = ("created_at", "flagged_by")
    actions = ['mark_reviewed', 'mark_resolved', 'mark_dismissed']
    
    fieldsets = (
        ('Flag Information', {
            'fields': ('message', 'flagged_by', 'reason', 'description', 'created_at')
        }),
        ('Review', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'admin_notes')
        }),
    )
    
    def message_preview(self, obj):
        if obj.message:
            preview = obj.message.body[:50]
            return f"Message #{obj.message.id}: {preview}..."
        return "N/A"
    message_preview.short_description = 'Flagged Message'
    
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