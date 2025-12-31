# Add these to your app/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name='home'),
    path("logout", views.logout_view, name='logout'),
    path('setup/', views.first_time_setup, name='first_time_setup'),
    path('suspended/', views.ban_page, name='ban_page'),
    path('dashboard/', views.dashboard, name='dashboard'),    
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),    
    path('ban/<int:user_id>/', views.ban_user, name='ban_user'),
    path('appeals/', views.admin_open_appeals, name='admin_open_appeals'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/delete/', views.delete_profile, name='delete_profile'),
    path('listings/', views.public_listings, name='public_listings'),
    path('listings/<int:listing_id>/', views.listing_detail, name='listing_detail'),
    path('listings/<int:listing_id>/edit/', views.edit_listing, name='edit_listing'),
    path('listings/<int:listing_id>/delete/', views.delete_listing, name='delete_listing'),
    path('listings/<int:listing_id>/toggle/', views.toggle_listing_status, name='toggle_listing_status'),
    path('listings/<int:listing_id>/flag/', views.flag_listing, name='flag_listing'),
    path('admin/review-flags/', views.admin_review_flags, name='admin_review_flags'),
    path('admin/flags/<int:flag_id>/resolve/', views.resolve_flag, name='resolve_flag'),
]