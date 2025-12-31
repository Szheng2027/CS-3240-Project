from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from .models import Notification
import json


@login_required
@require_http_methods(["GET"])
def get_notifications(request):
    """
    API endpoint to fetch unread notifications for the current user.
    Returns JSON with notifications list.
    """
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).order_by('-created_at')[:10]  # Limit to 10 most recent
    
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'link': notif.link,
            'created_at': notif.created_at.isoformat(),
            'sender_name': notif.sender.profile.get_display_name() if notif.sender else None,
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count()
    })


@login_required
@require_http_methods(["POST"])
def mark_as_read(request, notification_id):
    """
    Mark a specific notification as read.
    """
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)


@login_required
@require_http_methods(["POST"])
def mark_all_as_read(request):
    """
    Mark all notifications for the current user as read.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["GET"])
def get_unread_count(request):
    """
    Get count of unread notifications.
    """
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})


@login_required
@require_http_methods(["GET"])
def poll_new_notifications(request):
    """
    Poll for new notifications since the last check.
    Used for real-time notification display.
    """
    last_id = request.GET.get('last_id', 0)
    try:
        last_id = int(last_id)
    except (ValueError, TypeError):
        last_id = 0
    
    # Get new unread notifications since last_id
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        id__gt=last_id
    ).order_by('created_at')[:5]  # Limit to avoid overwhelming
    
    notifications_data = []
    for notif in notifications:
        notifications_data.append({
            'id': notif.id,
            'type': notif.notification_type,
            'title': notif.title,
            'message': notif.message,
            'link': notif.link,
            'created_at': notif.created_at.isoformat(),
            'sender_name': notif.sender.profile.get_display_name() if notif.sender else None,
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count()
    })
