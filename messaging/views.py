from django.shortcuts import render
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from .models import Thread, Message, MessageFlag
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse
from django.core.mail import send_mail
from django.contrib import messages as django_messages
from django.utils import timezone
from functools import wraps
from notifications.models import Notification
# Create your views here.

User = get_user_model()
def isBanned(view_func):
    @wraps(view_func)
    def banned(request, *args, **kwargs):
        if request.user.profile.banned:
            return redirect('ban_page')
        return view_func(request, *args, **kwargs)
    return banned
@login_required(login_url='/accounts/google/login/')
@isBanned
@never_cache
def inbox(request):
    # Order threads by most recent message instead of updated_at
    from django.db.models import Max
    
    threads = Thread.objects.filter(
        participants=request.user
    ).prefetch_related(
        'participants__profile'
    ).annotate(
        latest_message_time=Max('messages__created_at')
    ).order_by('-latest_message_time', '-created_at')
    
    thread_list = []
    for thread in threads:
        # Get all participants and filter out current user
        participants = list(thread.participants.all())
        other_participants = [p for p in participants if p.id != request.user.id]
        
        # Add computed properties
        if other_participants:
            thread.other_participant = other_participants[0]
        else:
            thread.other_participant = None
        
        thread.is_group = len(participants) > 2
        
        # Count unread messages for this thread
        unread_messages = thread.messages.filter(
            is_read=False
        ).exclude(sender=request.user)
        thread.unread_count = unread_messages.count()
        
        thread_list.append(thread)
    
    return render(request, 'messaging/inbox.html', {'threads': thread_list})
@login_required(login_url='/accounts/google/login/')
@isBanned
@never_cache
def thread_detail(request, thread_id):
    thread = get_object_or_404(Thread, pk=thread_id, participants=request.user)
    thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    if request.method == "POST":
        body = request.POST.get("body")
        if body:
            Message.objects.create(thread=thread, sender=request.user, body=body)
            thread.save()

            sender_name = request.user.profile.get_display_name()
            from_email = settings.DEFAULT_FROM_EMAIL
            thread_url = request.build_absolute_uri(reverse("messaging:thread_detail", args=[thread.id]))

            recipients = thread.participants.exclude(pk=request.user.pk)
            for recipient in recipients:
                try:
                    profile = recipient.profile
                    wants_email = getattr(profile, "email_notifications", False)
                except Exception:
                    wants_email = False

                if wants_email and recipient.email:
                    subject = f"New message from {sender_name}"
                    message = (
                        f"Hi {recipient.profile.get_display_name()},\n\n"
                        f"You have a new message from {sender_name}:\n\n"
                        f"{body[:300]}\n\n"
                        f"View the full conversation: {thread_url}\n\n"
                        "To stop these notifications, update your preferences in your profile."
                    )
                    try:
                        send_mail(subject, message, from_email, [recipient.email], fail_silently=True)
                    except Exception:
                        pass

                # Create in-app notification
                Notification.create_notification(
                    recipient=recipient,
                    notification_type='new_message',
                    title=f"New message from {sender_name}",
                    message=body[:150] + ('...' if len(body) > 150 else ''),
                    link=thread_url,
                    sender=request.user
                )

            return redirect("messaging:thread_detail", thread_id=thread_id)

    return render(request, "messaging/thread_detail.html", {"thread": thread})

@login_required(login_url='/accounts/google/login/')
@isBanned
@never_cache
def start_thread(request, username):
    other_user = get_object_or_404(User, username=username)
    
    thread = (
        Thread.objects
        .filter(participants=request.user)
        .filter(participants=other_user)
        .distinct()
        .first()
    )

    is_new_thread = thread is None
    if not thread:
        thread = Thread.objects.create()
        thread.participants.add(request.user, other_user)
    
    thread.participants.add(request.user, other_user)

    # Send notification to the other user when starting a new conversation
    if is_new_thread:
        sender_name = request.user.profile.get_display_name()
        thread_url = reverse("messaging:thread_detail", args=[thread.id])
        Notification.create_notification(
            recipient=other_user,
            notification_type='message_request',
            title=f"{sender_name} started a conversation",
            message=f"{sender_name} wants to chat with you!",
            link=thread_url,
            sender=request.user
        )

    return redirect("messaging:thread_detail", thread_id=thread.id)

@login_required(login_url='/accounts/google/login/')
@never_cache
def flag_message(request, message_id):
    """
    Flag a message as inappropriate.
    """
    message = get_object_or_404(Message, pk=message_id)
    
    # Prevent users from flagging their own messages
    if message.sender == request.user:
        django_messages.error(request, "You cannot flag your own message.")
        return redirect('messaging:thread_detail', thread_id=message.thread.id)
    
    # Check if user is part of the thread
    if request.user not in message.thread.participants.all():
        django_messages.error(request, "You don't have access to this message.")
        return redirect('messaging:inbox')
    
    # Check if user already flagged this message
    existing_flag = MessageFlag.objects.filter(
        message=message,
        flagged_by=request.user
    ).exists()
    
    if existing_flag:
        django_messages.warning(request, "You have already flagged this message.")
        return redirect('messaging:thread_detail', thread_id=message.thread.id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        description = request.POST.get('description', '')
        
        MessageFlag.objects.create(
            message=message,
            flagged_by=request.user,
            reason=reason,
            description=description
        )
        
        django_messages.success(request, 'Thank you for reporting this message. Our team will review it shortly.')
        return redirect('messaging:thread_detail', thread_id=message.thread.id)
    
    context = {
        'message': message,
        'reasons': MessageFlag.REASON_CHOICES,
    }
    
    return render(request, 'messaging/flag_message.html', context)

def _is_admin(u):
    return u.is_staff or u.is_superuser

@login_required(login_url='/accounts/google/login/')
@never_cache
def admin_review_message_flags(request):
    """
    Admin view to review flagged messages (requires staff/superuser).
    """
    if not (request.user.is_staff or request.user.is_superuser):
        django_messages.error(request, "You don't have permission to access this page.")
        return redirect('messaging:inbox')
    
    # Get all flags with status filter
    status_filter = request.GET.get('status', 'pending')
    
    message_flags = MessageFlag.objects.select_related('message', 'flagged_by', 'reviewed_by')
    
    if status_filter and status_filter != 'all':
        message_flags = message_flags.filter(status=status_filter)
    
    message_flags = message_flags.order_by('-created_at')
    
    context = {
        'message_flags': message_flags,
        'status_filter': status_filter,
        'status_choices': MessageFlag.STATUS_CHOICES,
    }
    
    return render(request, 'messaging/admin_review_message_flags.html', context)

@login_required(login_url='/accounts/google/login/')
@never_cache
def resolve_message_flag(request, flag_id):
    """
    Mark a message flag as resolved and optionally delete the message, warn, or ban user.
    """
    if not (request.user.is_staff or request.user.is_superuser):
        django_messages.error(request, "You don't have permission to perform this action.")
        return redirect('messaging:inbox')
    
    flag = get_object_or_404(MessageFlag, pk=flag_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        flag.reviewed_by = request.user
        flag.reviewed_at = timezone.now()
        flag.admin_notes = admin_notes
        
        if action == 'delete_and_resolve':
            # Delete the message and mark flag as resolved
            if flag.message:
                flag.message.delete()
            flag.status = 'resolved'
            django_messages.success(request, 'Message deleted and flag resolved.')
        
        elif action == 'delete_and_warn':
            # Delete message and send warning to user
            if flag.message:
                sender = flag.message.sender
                flag.message.delete()
                # TODO: Send warning email to user
                django_messages.success(request, f'Message deleted and warning sent to {sender.username}.')
            flag.status = 'resolved'
        
        elif action == 'delete_and_ban':
            # Delete message and ban user
            if flag.message:
                sender = flag.message.sender
                flag.message.delete()
                # Ban the user by setting is_active to False
                sender.is_active = False
                sender.save()
                # TODO: Send ban notification email
                django_messages.success(request, f'Message deleted and user {sender.username} has been banned.')
            flag.status = 'resolved'
        
        elif action == 'resolve_only':
            # Just resolve the flag without deleting
            flag.status = 'resolved'
            django_messages.success(request, 'Flag marked as resolved.')
        
        elif action == 'dismiss':
            # Dismiss the flag
            flag.status = 'dismissed'
            django_messages.success(request, 'Flag dismissed.')
        
        flag.save()
        return redirect('messaging:admin_review_message_flags')
    
    context = {
        'flag': flag,
    }
    
    return render(request, 'messaging/resolve_message_flag.html', context)
@login_required(login_url='/accounts/google/login/')
@never_cache
def create_group_thread(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        usernames_text = request.POST.get("participants", "").strip()
        usernames = [u.strip() for u in usernames_text.split(",") if u.strip()]
        thread = Thread.objects.create(name=name, creator=request.user)
        thread.participants.add(request.user)
        for username in usernames:
            try:
                user = User.objects.get(username=username)
                thread.participants.add(user)
            except User.DoesNotExist:
                continue

        return redirect("messaging:thread_detail", thread_id=thread.id)
    return render(request, "messaging/create_group_thread.html")


@login_required(login_url='/accounts/google/login/')
def add_member(request, thread_id):

    thread = get_object_or_404(Thread, pk=thread_id)

    if request.user != thread.creator:
        return redirect("messsage:thread_detail", thread_id=thread_id)

    if request.method == "POST":
        username = request.POST.get("username", "").strip()

        try:
            user = User.objects.get(username=username)

            if user in thread.participants.all():
                messages.warning(
                    request,
                    f"{user.profile.get_display_name()} is already in the group."
                )
            else:
                thread.participants.add(user)
                messages.success(
                    request,
                    f"Added {user.profile.get_display_name()} to the group."
                )

        except User.DoesNotExist:
            messages.error(
                request,
                f"'{username}' is not a valid user."
            )

        return redirect("messaging:thread_detail", thread_id=thread_id)
    return None


@login_required(login_url='/accounts/google/login/')
def remove_member(request, thread_id, user_id):
    thread = get_object_or_404(Thread, pk=thread_id)

    if request.user != thread.creator:
        return redirect("messaging:thread_detail", thread_id=thread_id)

    user = get_object_or_404(User, pk=user_id)

    if user != thread.creator:
        thread.participants.remove(user)
        messages.success(
            request,
            f"Removed {user.profile.get_display_name()} from the group."
        )
    else:
        messages.warning(
            request,
            "You cannot remove yourself as the group creator."
        )

    return redirect("messaging:thread_detail", thread_id=thread_id)
# ADD/UPDATE these functions in your messaging/views.py

@login_required(login_url='/accounts/google/login/')
@isBanned
@never_cache
def create_group_thread(request):
    """
    Create a group thread using participant emails instead of usernames.
    """
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        emails_text = request.POST.get("participants", "").strip()
        
        # Split emails by comma and clean them
        emails = [e.strip().lower() for e in emails_text.split(",") if e.strip()]
        
        # Validate we have at least one other participant
        if not emails:
            django_messages.error(request, "Please enter at least one participant email address.")
            return render(request, "messaging/create_group_thread.html")
        
        # Create the thread
        thread = Thread.objects.create(name=name, creator=request.user)
        thread.participants.add(request.user)
        
        # Track which emails were added successfully
        added_users = []
        invalid_emails = []
        
        for email in emails:
            try:
                user = User.objects.get(email=email)
                
                # Don't add the creator again
                if user != request.user:
                    thread.participants.add(user)
                    added_users.append(user.profile.get_display_name())
            except User.DoesNotExist:
                invalid_emails.append(email)
        
        # Show feedback messages
        if added_users:
            django_messages.success(request, f"Group created with {', '.join(added_users)}!")
        
        if invalid_emails:
            django_messages.warning(
                request, 
                f"Could not find users with these emails: {', '.join(invalid_emails)}"
            )
        
        return redirect("messaging:thread_detail", thread_id=thread.id)
    
    return render(request, "messaging/create_group_thread.html")


@login_required(login_url='/accounts/google/login/')
@never_cache
def add_member(request, thread_id):
    """
    Add a member to a group thread using their email address.
    """
    thread = get_object_or_404(Thread, pk=thread_id)

    if request.user != thread.creator:
        return redirect("messaging:thread_detail", thread_id=thread_id)

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()

        try:
            user = User.objects.get(email=email)

            if user in thread.participants.all():
                django_messages.warning(
                    request,
                    f"{user.profile.get_display_name()} is already in the group."
                )
            else:
                thread.participants.add(user)
                django_messages.success(
                    request,
                    f"Added {user.profile.get_display_name()} to the group."
                )

        except User.DoesNotExist:
            django_messages.error(
                request,
                f"No user found with email '{email}'. Make sure they've signed up."
            )

        return redirect("messaging:thread_detail", thread_id=thread_id)
    return None


# KEEP THIS remove_member function AS-IS (it already works well)
@login_required(login_url='/accounts/google/login/')
def remove_member(request, thread_id, user_id):
    thread = get_object_or_404(Thread, pk=thread_id)

    if request.user != thread.creator:
        return redirect("messaging:thread_detail", thread_id=thread_id)

    user = get_object_or_404(User, pk=user_id)

    if user != thread.creator:
        thread.participants.remove(user)
        django_messages.success(
            request,
            f"Removed {user.profile.get_display_name()} from the group."
        )
    else:
        django_messages.warning(
            request,
            "You cannot remove yourself as the group creator."
        )

    return redirect("messaging:thread_detail", thread_id=thread_id)