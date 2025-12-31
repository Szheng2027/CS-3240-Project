from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('api/get/', views.get_notifications, name='get_notifications'),
    path('api/poll/', views.poll_new_notifications, name='poll_notifications'),
    path('api/mark-read/<int:notification_id>/', views.mark_as_read, name='mark_as_read'),
    path('api/mark-all-read/', views.mark_all_as_read, name='mark_all_as_read'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
]
