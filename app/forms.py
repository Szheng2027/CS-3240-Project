from django import forms
from .models import Profile, Listing, BanAppeal

class FirstTimeSetupForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'First name', 'class': 'form-control'}),
        label='First Name'
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Last name', 'class': 'form-control'}),
        label='Last Name'
    )
    
    class Meta:
        model = Profile
        fields = ['first_name', 'last_name', 'image', 'school_year']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'onchange': 'previewImage(this)',
            }),
            'school_year': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'image': 'Profile Picture (Optional)',
            'school_year': 'School Year',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
    
    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.save()
        profile.setup_complete = True
        if commit:
            profile.save()
        return profile

class BanAppealForm(forms.ModelForm):
    class Meta:
        model = BanAppeal
        fields = ["subject", "message", "evidence"]
        widgets = {
            "subject": forms.TextInput(attrs={"class": "form-control", "placeholder": "Short summary"}),
            "message": forms.Textarea(attrs={"class": "form-control", "rows": 6, "placeholder": "Explain why the ban should be lifted"}),
            "evidence": forms.FileInput(attrs={"class": "form-control", "accept": ".png,.jpg,.jpeg,.pdf"}),
        }
        labels = {
            "subject": "Appeal Subject",
            "message": "Appeal Message",
            "evidence": "Optional evidence (screenshots, documents)",
        }

class AdminBanForm(forms.Form):
    ban_reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={"rows":4, "class":"form-textarea"}),
        label="Ban reason"
    )

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'image', 'display_name', 'bio', 'sustainability_interests', 'school_year', 
            'email_notifications', 'inapp_notifications_enabled', 'notify_new_message',
            'notify_message_request', 'notify_group_added'
        ]
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'onchange': 'previewImage(this)',
            }),
            'display_name': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Tell us about yourself...',
                'class': 'form-control',
            }),
            'sustainability_interests': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'What sustainability topics interest you?',
                'class': 'form-control',
            }),
            'school_year': forms.Select(attrs={'class': 'form-control'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'inapp_notifications_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_new_message': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_message_request': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notify_group_added': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'display_name': 'Nickname/Handle (Optional)',
            'bio': 'Short Bio',
            'sustainability_interests': 'Sustainability Interests',
            'school_year': 'School Year',
            'email_notifications': 'Email Notifications',
            'inapp_notifications_enabled': 'Enable In-App Notifications',
            'notify_new_message': 'New Messages',
            'notify_message_request': 'Message Requests',
            'notify_group_added': 'Added to Group Chat',
        }

class ListingUpdateForm(forms.ModelForm):
    tags = forms.MultipleChoiceField(
        choices=Listing.TAG_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'tag-checkbox'}),
        required=False,
        label='Tags (Optional)',
        help_text='Select up to 2 tags to help others find your listing'
    )
    
    class Meta:
        model = Listing
        fields = ['title', 'description', 'category', 'condition', 'image', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Calculus Textbook, Mini Fridge, etc.',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe your item...',
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'onchange': 'previewImage(this)',
            }),
        }
        labels = {
            'title': 'Item Title',
            'description': 'Description',
            'category': 'Category',
            'condition': 'Condition',
            'image': 'Item Image (Optional)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['tags'].initial = self.instance.get_tags_list()
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags', [])
        if len(tags) > 2:
            raise forms.ValidationError('You can select up to 2 tags only.')
        return tags
    def get_tags_list(self):
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.set_tags_from_list(self.cleaned_data.get('tags', []))
        if commit:
            instance.save()
        return instance

class SimpleListingForm(forms.ModelForm):
    """Form for listing creation on dashboard - includes all fields"""
    tags = forms.MultipleChoiceField(
        choices=Listing.TAG_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'tag-checkbox'}),
        required=False,
        label='Tags (Optional)',
        help_text='Select up to 2 tags'
    )
    
    class Meta:
        model = Listing
        fields = ['title', 'description', 'category', 'condition', 'image', 'tags']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Reusable Shopping Bags',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe your item...',
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'onchange': 'previewImage(this)',
            }),
        }
        labels = {
            'title': 'Listing Title',
            'description': 'Description',
            'category': 'Category',
            'condition': 'Condition',
            'image': 'Image (Optional)',
        }
    
    def clean_tags(self):
        tags = self.cleaned_data.get('tags', [])
        if len(tags) > 2:
            raise forms.ValidationError('You can select up to 2 tags only.')
        return tags
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.set_tags_from_list(self.cleaned_data.get('tags', []))
        if commit:
            instance.save()
        return instance