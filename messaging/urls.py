# Update your messaging/urls.py to include these

from django.urls import path
from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("t/<int:thread_id>/", views.thread_detail, name="thread_detail"),
    path("start/<str:username>/", views.start_thread, name="start_thread"),
    path("group/create/", views.create_group_thread, name="group_conversation"),
    path("group/<int:thread_id>/add/", views.add_member, name="add_member"),
    path("group/<int:thread_id>/remove/<int:user_id>/", views.remove_member, name="remove_member"),
    path("message/<int:message_id>/flag/", views.flag_message, name="flag_message"),
    path("admin/review-flags/", views.admin_review_message_flags, name="admin_review_message_flags"),
    path("admin/flags/<int:flag_id>/resolve/", views.resolve_message_flag, name="resolve_message_flag"),
]