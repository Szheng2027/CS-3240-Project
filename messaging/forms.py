from django import forms

class SimpleThreadForm(forms.Form):
    name = forms.CharField(max_length=255, required=False)
    participants = forms.CharField(
        help_text="Enter usernames separated by commas"
    )