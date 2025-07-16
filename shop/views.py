from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Product, Order, OrderItem
from .forms import CheckoutForm

# Home page - show products with optional search and category filter
def home(request):
    query = request.GET.get('q', '')  # search term
    category = request.GET.get('category', '')

    products = Product.objects.all()

    if query:
        products = products.filter(name__icontains=query)

    if category and category != "All":
        products = products.filter(category__name__iexact=category)  # use related category name

    # For category dropdown in template
    categories = Product.objects.values_list('category__name', flat=True).distinct()

    return render(request, 'shop/home.html', {
        'products': products,
        'categories': categories,
        'selected_category': category,
        'search_query': query,
    })

# Product detail page
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'shop/product_detail.html', {'product': product})

# User signup view
from django.contrib.auth.forms import UserCreationForm

def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'shop/signup.html', {'form': form})

# Add product to cart (stored in session)
def add_to_cart(request, pk):
    cart = request.session.get('cart', {})
    cart[str(pk)] = cart.get(str(pk), 0) + 1
    request.session['cart'] = cart
    return redirect('cart_view')

# Remove product from cart
def remove_from_cart(request, pk):
    cart = request.session.get('cart', {})
    if str(pk) in cart:
        del cart[str(pk)]
    request.session['cart'] = cart
    return redirect('cart_view')

# View shopping cart
def cart_view(request):
    cart = request.session.get('cart', {})
    items = []
    total = 0
    for pk, qty in cart.items():
        product = get_object_or_404(Product, pk=pk)
        subtotal = product.price * qty
        items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
        total += subtotal
    return render(request, 'shop/cart.html', {'items': items, 'total': total})

# Update cart quantities from form POST
def update_cart(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})
        for key, value in request.POST.items():
            if key.startswith('qty_'):
                product_id = key.split('_')[1]
                if value.isdigit() and int(value) > 0:
                    cart[product_id] = int(value)
        request.session['cart'] = cart
    return redirect('cart_view')

# Clear entire cart
def clear_cart(request):
    request.session['cart'] = {}
    return redirect('cart_view')

# Checkout page - only for logged-in users
@login_required
def checkout(request):
    cart = request.session.get('cart', {})
    items = []
    total = 0
    for pk, qty in cart.items():
        product = get_object_or_404(Product, pk=pk)
        subtotal = product.price * qty
        items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
        total += subtotal

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Create Order
            order = Order.objects.create(
                user=request.user,
                full_name=form.cleaned_data['full_name'],
                email=form.cleaned_data['email'],
                address=form.cleaned_data['address'],
                phone=form.cleaned_data['phone'],
                total_price=total
            )
            # Save Order Items
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['qty'],
                    price=item['product'].price
                )
            # Clear cart after order placed
            request.session['cart'] = {}
            return render(request, 'shop/order_success.html', {'order': order})
    else:
        form = CheckoutForm()

    return render(request, 'shop/checkout.html', {'form': form, 'items': items, 'total': total})






from django.http import JsonResponse
from django.views.decorators.http import require_GET

@require_GET
def ajax_products(request):
    q = request.GET.get('q', '')
    sort = request.GET.get('sort', '')
    products = Product.objects.all()

    if q:
        products = products.filter(name__icontains=q)

    if sort == 'price_asc':
        products = products.order_by('price')
    elif sort == 'price_desc':
        products = products.order_by('-price')

    products_data = []
    for p in products:
        products_data.append({
            'id': p.id,
            'name': p.name,
            'price': str(p.price),
            'image': p.image.url if p.image else '',
        })

    return JsonResponse({'products': products_data})



from django.shortcuts import render, get_object_or_404, redirect
from .models import Product, Review
from .forms import ReviewForm
from django.contrib.auth.decorators import login_required

def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.order_by('-created_at')
    form = ReviewForm()

    if request.method == 'POST':
        if request.user.is_authenticated:
            form = ReviewForm(request.POST)
            if form.is_valid():
                review = form.save(commit=False)
                review.user = request.user
                review.product = product
                review.save()
                return redirect('product_detail', pk=product.pk)
        else:
            return redirect('login')

    context = {
        'product': product,
        'reviews': reviews,
        'form': form,
    }
    return render(request, 'shop/product_detail.html', context)





def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'shop/product_detail.html', {'product': product})




from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from .models import Product, Review

@login_required
@require_POST
def ajax_submit_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    rating = int(request.POST.get('rating', 0))
    comment = request.POST.get('comment', '').strip()

    if rating < 1 or rating > 5 or not comment:
        return JsonResponse({'success': False, 'error': 'Invalid rating or comment'})

    review, created = Review.objects.update_or_create(
        product=product,
        user=request.user,
        defaults={'rating': rating, 'comment': comment}
    )

    # Review summary
    reviews = Review.objects.filter(product=product)
    total_reviews = reviews.count()
    distinct_users = reviews.values('user').distinct().count()

    return JsonResponse({
        'success': True,
        'review': {
            'user': request.user.username,
            'rating': review.rating,
            'comment': review.comment,
            'created_at': review.created_at.strftime('%B %d, %Y %I:%M %p')
        },
        'summary': f"This product has {total_reviews} review(s) from {distinct_users} user(s)."
    })




from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import Order

@login_required
def my_orders(request):
    user_orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
    return render(request, 'shop/my_orders.html', {'orders': user_orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    items = order.items.all()  # related_name='items' in OrderItem model
    return render(request, 'shop/order_detail.html', {'order': order, 'items': items})


from django.contrib.auth.decorators import login_required

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
    return render(request, 'shop/order_history.html', {'orders': orders})

from .models import Offer
def offers(request):
    active_offers = Offer.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'shop/offers.html', {'offers': active_offers})
def preorder(request):
    # ekhane preorder page er content dite paro
    return render(request, 'shop/preorder.html')



