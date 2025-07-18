from django import forms
from .models import Review, Preorder

class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=100, label="Full Name")
    email = forms.EmailField(label="Email")
    address = forms.CharField(widget=forms.Textarea, label="Shipping Address")
    phone = forms.CharField(max_length=20, label="Phone Number")


class ReviewForm(forms.ModelForm):
    rating = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],  # i as int, str(i) as label
        widget=forms.RadioSelect,
        label='Rating'
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Write your review here...'
            }),
        }


class PreOrderForm(forms.ModelForm):
    class Meta:
        model = Preorder
        fields = '__all__'