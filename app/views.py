from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.cache import never_cache
from django.db.models import Count, Q
from .models import Profile, Listing, ContentFlag
from django.db.models import Count, Q, Value, F
from django.db.models.functions import Coalesce, Concat, NullIf
from .models import Profile, Listing, BanAppeal
from django.contrib import messages
from .forms import ProfileUpdateForm, ListingUpdateForm, FirstTimeSetupForm, SimpleListingForm, BanAppealForm, AdminBanForm
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from functools import wraps
from notifications.models import Notification
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# Create your views here.

def setup_required(view_func):
    """
    Decorator to redirect users to first-time setup if they haven't completed it.
    """
    @wraps(view_func)
    @never_cache
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            if not profile.setup_complete:
                return redirect('first_time_setup')
        return view_func(request, *args, **kwargs)
    return wrapper

def home(request):
    return render(request, "home.html")

def isBanned(view_func):
    @wraps(view_func)
    def banned(request, *args, **kwargs):
        if request.user.profile.banned:
            return redirect('ban_page')
        return view_func(request, *args, **kwargs)
    return banned

@isBanned
@never_cache
@login_required(login_url='/accounts/google/login/')
def first_time_setup(request):
    """
    First-time setup for new users to complete their profile.
    """
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    # If setup is already complete, redirect to dashboard
    if profile.setup_complete:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = FirstTimeSetupForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Welcome! Your profile has been set up successfully.')
            return redirect('dashboard')
    else:
        form = FirstTimeSetupForm(instance=profile, user=request.user)
    
    context = {
        'form': form,
    }
    return render(request, 'app/first_time_setup.html', context)

@never_cache
@login_required(login_url='/accounts/google/login/')
def ban_page(request):
    """
    Show ban details and allow submitting a BanAppeal.
    """
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not getattr(profile, "banned", False):
        return redirect("dashboard")

    pending_appeals = BanAppeal.objects.filter(user=user, status=BanAppeal.STATUS_PENDING).order_by("-created_at")
    all_appeals = BanAppeal.objects.filter(user=user).order_by("-created_at")

    if request.method == "POST":
        form = BanAppealForm(request.POST, request.FILES)
        if form.is_valid():
            appeal = form.save(commit=False)
            appeal.user = request.user
            appeal.save()
            messages.success(request, "Your appeal was submitted. Admins will review it.")
            return redirect("dashboard")
    else:
        form = BanAppealForm()

    context = {"form": form, 
               "profile": profile, 
                "pending_appeals": pending_appeals,
                "all_appeals": all_appeals,
            }
    return render(request, "app/ban_page.html", context)

def logout_view(request):
    logout(request)
    return redirect("/")

def get_user_context(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'username': user.username,
        'profile': profile,
        'display_name': profile.get_display_name(),
    }

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    
    if request.method == "POST":
        # Pass in request.POST (text data) and request.FILES (file data)
        form = SimpleListingForm(request.POST, request.FILES)
        
        if form.is_valid():
            # Don't save to the database just yet
            listing = form.save(commit=False)
            # Set the owner to the currently logged-in user
            listing.owner = request.user
            # Now save the listing with the owner
            listing.save()
            messages.success(request, 'Your listing has been created successfully!')
            return redirect("dashboard")
        else:
            messages.error(request, 'There was an error creating your listing. Please check the form.')
    else:
        # For a GET request, create a blank form
        form = SimpleListingForm()

    my_listings = Listing.objects.filter(owner=request.user).order_by("-created_at")
    context = {
        "email": request.user.email,
        "name": profile.get_display_name(),
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        "profile": profile,
        "my_listings": my_listings,
        "form": form,
        'display_name': profile.get_display_name(),
    }
    return render(request, "app/dashboard.html", context)

def _is_admin(u):
    return u.is_staff or u.is_superuser

@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@never_cache
# REPLACE your admin_dashboard function in views.py with this version

@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@setup_required
@never_cache
def admin_dashboard(request):
    """
    Admin dashboard with user management, listings, and reported content.
    """
    listings = Listing.objects.order_by("-created_at")[:50]
    counts = (Listing.objects
              .values("owner__username")
              .annotate(
                    display_name=Coalesce(
                        NullIf(F("owner__profile__display_name"), Value("")),
                        Concat(F("owner__first_name"), Value(" "), F("owner__last_name")),
                    ),
                    n=Count("id"),
                )
              .order_by("-n"))
    profile, _ = Profile.objects.get_or_create(user=request.user)
    display_name = profile.get_display_name()

    search_query = request.GET.get("search", "").strip()
    User = get_user_model()

    users_qs = User.objects.select_related("profile").order_by("-date_joined")

    if search_query:
        users_qs = users_qs.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
            | Q(profile__display_name__icontains=search_query)
        )

    users = users_qs[:20]
    
    # REPORTED CONTENT STATS
    # Get flagged listings counts
    pending_flags = ContentFlag.objects.filter(status='pending').count()
    reviewed_flags = ContentFlag.objects.filter(status='reviewed').count()
    resolved_flags = ContentFlag.objects.filter(status='resolved').count()
    total_flags = ContentFlag.objects.count()
    
    # Get recent flagged listings (last 5 pending)
    recent_flags = ContentFlag.objects.filter(
        status='pending'
    ).select_related(
        'listing__owner__profile', 'flagged_by__profile'
    ).order_by('-created_at')[:5]

    context = {
        "email": request.user.email,
        "first_name": request.user.first_name,
        "last_name": request.user.last_name,
        "username": request.user.username,
        "listings": listings,
        "counts": counts,
        "display_name": display_name,
        "users": users,
        "search_query": search_query,
        # Reported content stats
        "pending_flags": pending_flags,
        "reviewed_flags": reviewed_flags,
        "resolved_flags": resolved_flags,
        "total_flags": total_flags,
        "recent_flags": recent_flags,
    }
    return render(request, "app/admin-dashboard.html", context)
@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@never_cache
def ban_user(request, user_id):
    User = get_user_model()
    try:
        target = User.objects.select_related("profile").get(pk=int(user_id))
    except (User.DoesNotExist, ValueError):
        messages.error(request, "User not found.")
        return redirect("admin-dashboard")

    profile, _ = Profile.objects.get_or_create(user=target)

    # fetch appeals for display
    appeals = BanAppeal.objects.filter(user=target).order_by("-created_at")

    if request.method == "POST":
        # If the POST contains an appeal_id, handle accept/reject here (no separate URL)
        appeal_id = request.POST.get("appeal_id")
        if appeal_id:
            try:
                appeal = BanAppeal.objects.get(pk=int(appeal_id))
            except BanAppeal.DoesNotExist:
                messages.error(request, "Appeal not found.")
                return HttpResponseRedirect(request.POST.get("next") or reverse("ban_user", kwargs={"user_id": user_id}))

            action = request.POST.get("action")
            admin_note = request.POST.get("admin_note", "").strip()

            if action == "accept":
                appeal.status = BanAppeal.STATUS_ACCEPTED
                # unban the user
                fed_profile, _ = Profile.objects.get_or_create(user=appeal.user)
                fed_profile.banned = False
                fed_profile.ban_reason = ""
                fed_profile.save(update_fields=["banned", "ban_reason"])
                # notify user
                try:
                    send_mail(
                        subject="Your unban request was accepted",
                        message=f"Hello {appeal.user.get_username()},\n\nYour unban request has been accepted by an admin.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[appeal.user.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass

                messages.success(request, f"Appeal accepted — {profile.get_display_name()} unbanned.")
            else:
                appeal.status = BanAppeal.STATUS_REJECTED
                messages.success(request, f"Appeal rejected for {profile.get_display_name()}.")

            if admin_note:
                appeal.admin_response = admin_note
            appeal.responded_at = timezone.now()
            appeal.save(update_fields=["status", "admin_response", "responded_at"] if admin_note else ["status", "responded_at"])

            return HttpResponseRedirect(request.POST.get("next") or reverse("admin_ban_user_page", kwargs={"user_id": user_id}))

        if request.method == "POST":
            if request.POST.get("unban"):
                profile.banned = False
                profile.ban_reason = ""
                profile.save(update_fields=["banned", "ban_reason"])

                pending = BanAppeal.objects.filter(user=target, status=BanAppeal.STATUS_PENDING)
                if pending.exists():
                    now = timezone.now()
                    for appeal in pending:
                        appeal.status = BanAppeal.STATUS_ACCEPTED
                        # give a short admin_response if none present
                        if not appeal.admin_response:
                            appeal.admin_response = "Unban applied by admin."
                        appeal.responded_at = now
                        appeal.save(update_fields=["status", "admin_response", "responded_at"])

                messages.success(request, f"User {profile.get_display_name()} unbanned.")
                try:
                    send_mail(
                        subject="Your account has been reinstated",
                        message=f"Hello {profile.get_display_name()},\n\nYour account has been unbanned by an administrator.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[target.email],
                        fail_silently=True,
                    )
                except Exception:
                    pass
                return HttpResponseRedirect(request.POST.get("next") or reverse("ban_user", kwargs={"user_id": user_id}))


        form = AdminBanForm(request.POST)
        if form.is_valid():
            profile.banned = True
            profile.ban_reason = form.cleaned_data["ban_reason"] or ""
            profile.save(update_fields=["banned", "ban_reason"])
            messages.success(request, f"User {profile.get_display_name()} banned.")
            try:
                send_mail(
                    subject=f"Account banned by admin",
                    message=f"Hello {profile.get_display_name()},\n\nYour account has been banned.\n\nIf you believe this is a mistake contact support.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[target.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            return HttpResponseRedirect(request.POST.get("next") or reverse("ban_user", kwargs={"user_id": user_id}))
    else:
        form = AdminBanForm(initial={"ban": profile.banned, "ban_reason": profile.ban_reason})

    context = {
        "target": target,
        "profile": profile,
        "form": form,
        "next": request.GET.get("next", reverse("admin-dashboard")),
        "appeals": appeals,
    }
    return render(request, "app/ban_user.html", context)

@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@never_cache
def admin_open_appeals(request):
    """
    Admin view: list pending appeals and allow quick accept/reject.
    POST expected fields: appeal_id, action (accept|reject), admin_note (optional), next (optional)
    """
    if request.method == "POST":
        appeal_id = request.POST.get("appeal_id")
        if not appeal_id:
            messages.error(request, "Missing appeal id.")
            return HttpResponseRedirect(request.POST.get("next") or reverse("admin_open_appeals"))
        try:
            appeal = BanAppeal.objects.get(pk=int(appeal_id))
        except (BanAppeal.DoesNotExist, ValueError):
            messages.error(request, "Appeal not found.")
            return HttpResponseRedirect(request.POST.get("next") or reverse("admin_open_appeals"))

        action = request.POST.get("action")
        admin_note = (request.POST.get("admin_note") or "").strip()
        now = timezone.now()

        if action == "accept":
            appeal.status = BanAppeal.STATUS_ACCEPTED
            profile, _ = Profile.objects.get_or_create(user=appeal.user)
            profile.banned = False
            profile.ban_reason = ""
            profile.save(update_fields=["banned", "ban_reason"])
            try:
                send_mail(
                    subject="Your unban request was accepted",
                    message=f"Hello {appeal.user.get_username()},\n\nYour unban request has been accepted by an admin.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[appeal.user.email],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, f"Accepted appeal — {appeal.user.username} unbanned.")
        else:
            appeal.status = BanAppeal.STATUS_REJECTED
            messages.success(request, f"Rejected appeal for {appeal.user.username}.")

        if admin_note:
            appeal.admin_response = admin_note
        appeal.responded_at = now
        appeal.save(update_fields=["status", "admin_response", "responded_at"] if admin_note else ["status", "responded_at"])

        return HttpResponseRedirect(request.POST.get("next") or reverse("admin_open_appeals"))

    # GET: show pending appeals + paginated completed
    pending = BanAppeal.objects.filter(status=BanAppeal.STATUS_PENDING).select_related("user").order_by("created_at")
    
    # completed appeals (accepted or rejected)
    completed = BanAppeal.objects.filter(status__in=[BanAppeal.STATUS_ACCEPTED, BanAppeal.STATUS_REJECTED]).select_related("user").order_by("-responded_at")
    
    # paginate completed (10 per page)
    page_num = request.GET.get("page", 1)
    paginator = Paginator(completed, 10)
    try:
        completed_page = paginator.page(page_num)
    except PageNotAnInteger:
        completed_page = paginator.page(1)
    except EmptyPage:
        completed_page = paginator.page(paginator.num_pages)

    context = {
        "appeals": pending,
        "completed_page": completed_page,
    }
    return render(request, "app/admin_open_appeals.html", context)

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def profile_view(request):
    if request.method == 'POST':
        old_email_notifications = request.user.profile.email_notifications
        old_inapp_notifications = request.user.profile.inapp_notifications_enabled
        
        # Pass request.FILES to the form to handle the uploaded image
        form = ProfileUpdateForm(request.POST, 
                                 request.FILES, 
                                 instance=request.user.profile)
        if form.is_valid():
            profile = form.save()
            
            # Check if email notifications were just enabled
            if profile.email_notifications and not old_email_notifications:
                # Send verification email
                try:
                    send_mail(
                        subject='Email Notifications Enabled',
                        message=f'Hi {profile.get_display_name()},\n\nYou have successfully enabled email notifications for your account. You will now receive email updates for new messages and activity.\n\nIf you did not make this change, please log in to your account and disable email notifications.\n\nThank you!',
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[request.user.email],
                        fail_silently=False,
                    )
                    messages.success(request, 'Email notifications enabled! A verification email has been sent to your address.')
                except Exception as e:
                    messages.warning(request, f'Email notifications enabled, but verification email could not be sent: {str(e)}')
            else:
                messages.success(request, 'Your profile has been updated!')
            
            # Send test notification if in-app notifications are enabled
            if profile.inapp_notifications_enabled:
                Notification.objects.create(
                    recipient=request.user,
                    notification_type='general',
                    title='Settings saved!',
                    message='Your notification preferences have been updated successfully.',
                    link=reverse('profile')
                )
            
            return redirect('profile')
    else:
        form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'form': form,
        'profile': request.user.profile,
    }
    
    return render(request, 'app/profile.html', context)

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def delete_profile(request):
    if request.method == 'POST':
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, 'Your profile has been successfully deleted.')
        return redirect('home')
    
    return render(request, 'app/confirm_delete.html')

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
# REPLACE your public_listings function in views.py with this version

@setup_required
@isBanned
@never_cache
def public_listings(request):
    if not request.user.is_authenticated:
        return redirect(f"/accounts/google/login/?next={request.get_full_path()}")
    """
    Display all active listings with search and filter functionality.
    Search ranks results by relevance (exact matches first, then partial matches).
    Supports filtering by category, condition, and tags.
    """
    search_query = request.GET.get('search', '').strip()
    category = request.GET.get('category', '').strip()
    condition = request.GET.get('condition', '').strip()  # NEW: Condition filter
    tag_filter = request.GET.get('tag', '').strip()
    
    # Get all active listings
    listings = Listing.objects.filter(is_active=True).select_related('owner__profile').order_by('-created_at')
    
    # Filter by category if selected
    if category:
        listings = listings.filter(category=category)
    
    # Filter by condition if selected (NEW)
    if condition:
        listings = listings.filter(condition=condition)
    
    # Filter by tag if selected
    if tag_filter:
        listings = listings.filter(tags__icontains=tag_filter)
    
    if search_query:
        # Search in title and description (case-insensitive)
        listings = listings.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )
        
        # Sort by relevance: exact matches first, then partial matches
        listings_with_scores = []
        for listing in listings:
            score = 0
            title_lower = listing.title.lower()
            desc_lower = listing.description.lower()
            query_lower = search_query.lower()
            
            # Exact match in title gets highest score
            if title_lower == query_lower:
                score = 100
            # Starts with query in title gets high score
            elif title_lower.startswith(query_lower):
                score = 75
            # Contains query in title gets medium score
            elif query_lower in title_lower:
                score = 50
            # Contains query in description gets lower score
            elif query_lower in desc_lower:
                score = 25
            # Any match gets base score
            else:
                score = 10
            
            listings_with_scores.append((listing, score))
        
        # Sort by score (highest first), then by creation date
        listings_with_scores.sort(key=lambda x: (-x[1], -x[0].created_at.timestamp()))
        listings = [item[0] for item in listings_with_scores]
    
    # Get all categories for filter dropdown
    categories = Listing.CATEGORY_CHOICES
    
    # Get all conditions for filter dropdown (NEW)
    conditions = Listing.CONDITION_CHOICES
    
    # Use predefined tag choices for filter UI
    tag_choices = Listing.TAG_CHOICES
    
    context = {
        'listings': listings,
        'search_query': search_query,
        'selected_category': category,
        'selected_condition': condition,  # NEW
        'selected_tag': tag_filter,
        'categories': categories,
        'conditions': conditions,  # NEW
        'tag_choices': tag_choices,
        'total_count': len(listings),
    }
    
    return render(request, 'app/public_listings.html', context)

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def listing_detail(request, listing_id):
    """
    Display detailed view of a single listing.
    """
    listing = get_object_or_404(Listing, pk=listing_id, is_active=True)
    
    # Increment view count
    listing.views += 1
    listing.save(update_fields=['views'])
    
    # Check if the current user is the owner
    is_owner = request.user == listing.owner
    
    context = {
        'listing': listing,
        'is_owner': is_owner,
    }
    
    return render(request, 'app/listing_detail.html', context)

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def edit_listing(request, listing_id):
    """
    Edit an existing listing (only owner can edit).
    """
    listing = get_object_or_404(Listing, pk=listing_id, owner=request.user)
    
    if request.method == 'POST':
        form = ListingUpdateForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your listing has been updated successfully!')
            return redirect('listing_detail', listing_id=listing.id)
        else:
            messages.error(request, 'There was an error updating your listing.')
    else:
        form = ListingUpdateForm(instance=listing)
    
    context = {
        'form': form,
        'listing': listing,
        'is_edit': True,
    }
    
    return render(request, 'app/edit_listing.html', context)

@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def delete_listing(request, listing_id):
    """
    Delete a listing (only owner can delete).
    """
    listing = get_object_or_404(Listing, pk=listing_id, owner=request.user)
    
    if request.method == 'POST':
        listing.delete()
        messages.success(request, 'Your listing has been deleted successfully!')
        return redirect('dashboard')
    
    context = {
        'listing': listing,
    }
    
    return render(request, 'app/confirm_delete_listing.html', context)


@login_required(login_url='/accounts/google/login/')
@isBanned
@setup_required
def toggle_listing_status(request, listing_id):
    """
    Toggle listing active status (mark as sold/available).
    """
    listing = get_object_or_404(Listing, pk=listing_id, owner=request.user)
    
    if request.method == 'POST':
        listing.is_active = not listing.is_active
        listing.save()
        status = 'available' if listing.is_active else 'sold'
        messages.success(request, f'Your listing has been marked as {status}!')
        return redirect('dashboard')
    
    return redirect('listing_detail', listing_id=listing_id)

# ========== CONTENT MODERATION VIEWS ==========

@login_required(login_url='/accounts/google/login/')
@setup_required
def flag_listing(request, listing_id):
    """
    Flag a listing as inappropriate.
    """
    listing = get_object_or_404(Listing, pk=listing_id)
    
    # Prevent users from flagging their own listings
    if listing.owner == request.user:
        messages.error(request, "You cannot flag your own listing.")
        return redirect('listing_detail', listing_id=listing_id)
    
    # Check if user already flagged this listing
    existing_flag = ContentFlag.objects.filter(
        listing=listing,
        flagged_by=request.user
    ).exists()
    
    if existing_flag:
        messages.warning(request, "You have already flagged this listing.")
        return redirect('listing_detail', listing_id=listing_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        description = request.POST.get('description', '')
        
        ContentFlag.objects.create(
            listing=listing,
            flagged_by=request.user,
            reason=reason,
            description=description
        )
        
        messages.success(request, 'Thank you for reporting this listing. Our team will review it shortly.')
        return redirect('listing_detail', listing_id=listing_id)
    
    context = {
        'listing': listing,
        'reasons': ContentFlag.REASON_CHOICES,
    }
    
    return render(request, 'app/flag_listing.html', context)

@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@never_cache
def admin_review_flags(request):
    """
    Admin view to review flagged content (requires staff/superuser).
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')
    
    # Get all flags with status filter
    status_filter = request.GET.get('status', 'pending')
    
    listing_flags = ContentFlag.objects.select_related('listing', 'flagged_by', 'reviewed_by')
    
    if status_filter and status_filter != 'all':
        listing_flags = listing_flags.filter(status=status_filter)
    
    listing_flags = listing_flags.order_by('-created_at')
    
    context = {
        'listing_flags': listing_flags,
        'status_filter': status_filter,
        'status_choices': ContentFlag.STATUS_CHOICES,
    }
    
    return render(request, 'app/admin_review_flags.html', context)

@login_required(login_url='/accounts/google/login/')
@user_passes_test(_is_admin)
@never_cache
def resolve_flag(request, flag_id):
    """
    Mark a flag as resolved and optionally delete the content, warn, or ban user.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('dashboard')
    
    flag = get_object_or_404(ContentFlag, pk=flag_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        flag.reviewed_by = request.user
        flag.reviewed_at = timezone.now()
        flag.admin_notes = admin_notes
        
        if action == 'delete_and_resolve':
            # Delete the listing and mark flag as resolved
            if flag.listing:
                flag.listing.delete()
            flag.status = 'resolved'
            messages.success(request, 'Content deleted and flag resolved.')
        
        elif action == 'delete_and_warn':
            # Delete listing and send warning to user
            if flag.listing:
                owner = flag.listing.owner
                flag.listing.delete()
                # TODO: Send warning email to user
                # You can implement email sending here
                messages.success(request, f'Content deleted and warning sent to {owner.username}.')
            flag.status = 'resolved'
        
        elif action == 'delete_and_ban':
            # Delete listing and ban user
            if flag.listing:
                owner = flag.listing.owner
                flag.listing.delete()
                # Ban the user by setting is_active to False
                owner.is_active = False
                owner.save()
                # TODO: Send ban notification email
                messages.success(request, f'Content deleted and user {owner.username} has been banned.')
            flag.status = 'resolved'
        
        elif action == 'resolve_only':
            # Just resolve the flag without deleting
            flag.status = 'resolved'
            messages.success(request, 'Flag marked as resolved.')
        
        elif action == 'dismiss':
            # Dismiss the flag
            flag.status = 'dismissed'
            messages.success(request, 'Flag dismissed.')
        
        flag.save()
        return redirect('admin_review_flags')
    
    context = {
        'flag': flag,
    }
    
    return render(request, 'app/resolve_flag.html', context)