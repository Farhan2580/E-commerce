from django import forms
from .models import Review, Preorder, SavedAddress


class CheckoutForm(forms.Form):
    delivery_zone = forms.ModelChoiceField(queryset=None, required=False, label='Delivery area', empty_label='Choose your delivery area')
    coupon_code = forms.CharField(max_length=40, required=False, label='Coupon code', help_text='Discount is validated again when your order is placed.')
    full_name = forms.CharField(max_length=100, label="Full Name")
    email = forms.EmailField(label="Email")
    address = forms.CharField(max_length=2000,
                              widget=forms.Textarea(attrs={'rows': 3, 'autocomplete': 'street-address'}),
                              label="Shipping Address")
    phone = forms.CharField(max_length=20, label="Phone Number")
    checkout_token = forms.UUIDField(widget=forms.HiddenInput)
    payment_method = forms.ChoiceField(
        choices=[('COD', 'Cash on Delivery'), ('BKASH', 'bKash — manual transfer verification')])
    bkash_number = forms.RegexField(regex=r'^\+?\d{10,15}$', max_length=15, required=False, label='Sender bKash number')
    trx_id = forms.CharField(max_length=50, required=False, label='Transaction reference')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .services import enabled_payment_methods
        from .models import DeliveryZone
        self.fields['delivery_zone'].queryset = DeliveryZone.objects.filter(active=True)
        self.fields['delivery_zone'].label_from_instance = lambda zone: f'{zone.name} · BDT {zone.shipping_price} · {zone.estimate}'
        self.fields['delivery_zone'].required = self.fields['delivery_zone'].queryset.exists()
        self.fields['delivery_zone'].help_text = 'Choose an area, then review delivery & total before placing your order.'
        if not self.fields['delivery_zone'].required:
            self.fields['delivery_zone'].widget = forms.HiddenInput()
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['phone'].widget.attrs.update({'autocomplete': 'tel', 'type': 'tel'})
        self.fields['payment_method'].choices = enabled_payment_methods()

    def clean_payment_method(self):
        from .services import enabled_payment_methods
        method = self.cleaned_data['payment_method']
        if method not in dict(enabled_payment_methods()):
            raise forms.ValidationError('This payment method is unavailable. Choose another method.')
        return method

    def clean_phone(self):
        import re
        value = self.cleaned_data['phone'].strip()
        if not re.fullmatch(r'\+?[\d\s-]{7,20}', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15:
            raise forms.ValidationError('Enter a valid phone number.')
        return value

    def clean_full_name(self):
        value = self.cleaned_data['full_name'].strip()
        if len(value) < 2 or not any(char.isalpha() for char in value):
            raise forms.ValidationError('Enter your full name using letters.')
        return value

    def clean_address(self):
        value = self.cleaned_data['address'].strip()
        if len(value) < 5 or not any(char.isalnum() for char in value):
            raise forms.ValidationError('Enter a shipping address including your area and delivery location.')
        return value

    def clean(self):
        data = super().clean()
        return data


class ManualReferenceForm(forms.Form):
    reference = forms.RegexField(regex=r'^[A-Za-z0-9]{6,30}$', max_length=30,
        label='bKash transaction reference', help_text='Use the transaction reference from your receipt. Do not enter a PIN or OTP.')

    def clean_reference(self):
        value = self.cleaned_data['reference'].upper()
        if value.isdecimal():
            raise forms.ValidationError('Enter the alphanumeric transaction reference, not a PIN or OTP.')
        return value


class ReviewForm(forms.ModelForm):
    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'image'):
            if image.size > 5 * 1024 * 1024 or image.image.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise forms.ValidationError('Choose a JPEG, PNG or WebP photo up to 5 MB.')
        return image

    rating = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],  # i as int, str(i) as label
        widget=forms.RadioSelect,
        label='Rating'
    )

    class Meta:
        model = Review
        fields = ['rating', 'comment', 'image']
        help_texts = {'image': 'Optional product photo. JPEG, PNG or WebP, up to 5 MB.'}
        widgets = {
            'comment': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Write your review here...'
            }),
        }


class PreOrderForm(forms.ModelForm):
    class Meta:
        model = Preorder
        fields = ['name', 'email', 'phone', 'address', 'product_name', 'product_details', 'image']


class AddressForm(forms.ModelForm):
    clean_phone = CheckoutForm.clean_phone
    clean_full_name = CheckoutForm.clean_full_name
    clean_address = CheckoutForm.clean_address

    class Meta:
        model = SavedAddress
        fields = ['label', 'full_name', 'phone', 'address']
        widgets = {'address': forms.Textarea(attrs={'rows': 3})}


class SupportForm(forms.Form):
    name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    phone = forms.CharField(max_length=20, widget=forms.TextInput(attrs={'autocomplete': 'tel', 'type': 'tel'}))
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    topic = forms.ChoiceField(choices=[('contact', 'General enquiry'), ('warranty', 'Warranty enquiry')])
    message = forms.CharField(min_length=10, max_length=5000, widget=forms.Textarea(attrs={'rows': 6}))
    website = forms.CharField(required=False, label='Leave this field empty', widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))
    form_token = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, nonce, scope='contact', language='en', **kwargs):
        super().__init__(*args, **kwargs)
        from .support import UI
        self.nonce, self.scope = nonce, scope
        self.language = 'en'
        ui = UI['en']
        for field in ['name', 'phone', 'email', 'message']:
            self.fields[field].label = ui[field]
        self.fields['topic'].label = ui['contact_topic']
        self.fields['topic'].choices = [('contact', ui['general']), ('warranty', ui['warranty_topic'])]
        if scope.startswith('order:'):
            self.fields.pop('topic')

    def clean_phone(self):
        try:
            return CheckoutForm.clean_phone(self)
        except forms.ValidationError:
            raise forms.ValidationError('Enter a valid phone number.')

    def clean_website(self):
        if self.cleaned_data['website']:
            raise forms.ValidationError('Unable to accept this submission.')
        return ''

    def clean_form_token(self):
        from django.core import signing
        from uuid import UUID
        try:
            data = signing.loads(self.cleaned_data['form_token'], salt='shop.support.form', max_age=7200)
            if data['nonce'] != self.nonce or data['scope'] != self.scope:
                raise ValueError
            return UUID(data['token'])
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise forms.ValidationError('This form expired or belongs to another session. Refresh the page and try again.')
