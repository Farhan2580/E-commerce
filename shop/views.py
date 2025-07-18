from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from .models import Product, Order, OrderItem, Review, Offer, Preorder
from .forms import CheckoutForm, ReviewForm, PreOrderForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages

# Home Page with search and category filter
def home(request):
    query = request.GET.get('q', '')
    category = request.GET.get('category', '')
    products = Product.objects.all()

    if query:
        products = products.filter(name__icontains=query)
    if category and category != "All":
        products = products.filter(category__name__iexact=category)

    categories = Product.objects.values_list('category__name', flat=True).distinct()

    return render(request, 'shop/home.html', {
        'products': products,
        'categories': categories,
        'selected_category': category,
        'search_query': query,
    })

# Product List Page
def product_list(request):
    products = Product.objects.all()
    return render(request, 'shop/product_list.html', {'products': products})

# Product Detail Page with Reviews and Review submission
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

    return render(request, 'shop/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'form': form,
    })

# User Signup View
def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'shop/signup.html', {'form': form})

# Cart Management
def add_to_cart(request, pk):
    cart = request.session.get('cart', {})
    cart[str(pk)] = cart.get(str(pk), 0) + 1
    request.session['cart'] = cart
    return redirect('cart_view')

def remove_from_cart(request, pk):
    cart = request.session.get('cart', {})
    if str(pk) in cart:
        del cart[str(pk)]
    request.session['cart'] = cart
    return redirect('cart_view')

def cart_view(request):
    cart = request.session.get('cart', {})
    items, total = [], 0
    for pk, qty in cart.items():
        try:
            product = get_object_or_404(Product, pk=pk)
            subtotal = product.price * qty
            items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
            total += subtotal
        except:
            continue
    return render(request, 'shop/cart.html', {'items': items, 'total': total})

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

def clear_cart(request):
    request.session['cart'] = {}
    return redirect('cart_view')

# Checkout View
@login_required
def checkout(request):
    cart = request.session.get('cart', {})
    items, total = [], 0
    for pk, qty in cart.items():
        product = get_object_or_404(Product, pk=pk)
        subtotal = product.price * qty
        items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
        total += subtotal

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                user=request.user,
                full_name=form.cleaned_data['full_name'],
                email=form.cleaned_data['email'],
                address=form.cleaned_data['address'],
                phone=form.cleaned_data['phone'],
                total_price=total
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    quantity=item['qty'],
                    price=item['product'].price
                )
            request.session['cart'] = {}
            return redirect('my_orders')
    else:
        form = CheckoutForm()

    return render(request, 'shop/checkout.html', {'form': form, 'items': items, 'total': total})

# Offers Page
def offers(request):
    active_offers = Offer.objects.filter(is_active=True).order_by('-created_at')
    return render(request, 'shop/offers.html', {'offers': active_offers})

# Preorder View
@login_required
def preorder(request):
    if request.method == 'POST':
        form = PreOrderForm(request.POST, request.FILES)
        if form.is_valid():
            preorder = form.save(commit=False)
            preorder.user = request.user
            preorder.save()
            messages.success(request, "✅ Preorder placed successfully!")
            return redirect('order_history')
    else:
        form = PreOrderForm()
    return render(request, 'shop/preorder.html', {'form': form})

# Order History
@login_required
def my_orders(request):
    user_orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
    user_preorders = Preorder.objects.filter(user=request.user).order_by('-created_at')

    return render(request, 'shop/my_orders.html', {
        'orders': user_orders,
        'preorders': user_preorders,
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    items = order.items.all()
    return render(request, 'shop/order_detail.html', {'order': order, 'items': items})

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-date_ordered')
    preorders = Preorder.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'shop/order_history.html', {
        'orders': orders,
        'preorders': preorders,
    })

# AJAX Product Search
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
            'image': getattr(p.image, 'url', ''),
        })

    return JsonResponse({'products': products_data})

# AJAX Review Submit
@login_required
@require_POST
def ajax_submit_review(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        rating = int(request.POST.get('rating', 0))
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid rating format'})
    comment = request.POST.get('comment', '').strip()

    if rating < 1 or rating > 5 or not comment:
        return JsonResponse({'success': False, 'error': 'Invalid rating or comment'})

    review, created = Review.objects.update_or_create(
        product=product,
        user=request.user,
        defaults={'rating': rating, 'comment': comment}
    )

    total_reviews = Review.objects.filter(product=product).count()
    distinct_users = Review.objects.filter(product=product).values('user').distinct().count()

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

# Preorder Thank You Page
def preorder_thanks(request):
    return render(request, 'shop/preorder_thanks.html')  # ✅ fixed path


#new navbar

def laptop_desktop(request):
    return render(request, 'shop/laptop_desktop.html')

def phones_tablets(request):
    products = Product.objects.filter(category__name='Phones & Tablets')
    return render(request, 'shop/phones_tablets.html', {'products': products})

def sound_equipment(request):
    return render(request, 'shop/sound_equipment.html')

def power_accessories(request):
    return render(request, 'shop/power_accessories.html')

def fitness_wearable(request):
    return render(request, 'shop/fitness_wearable.html')

def smart_electronics(request):
    return render(request, 'shop/smart_electronics.html')
