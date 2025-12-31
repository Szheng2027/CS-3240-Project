from allauth.account.adapter import DefaultAccountAdapter
from django.urls import reverse

class AdminAccountAdapter(DefaultAccountAdapter):
    def get_login_redirect_url(self, request):
        if request.user.is_staff or request.user.is_superuser:
            return reverse('admin-dashboard')
        else:
            return reverse('dashboard')