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

def cart_count(request):
    cart = request.session.get('cart', {})
    # কার্টে থাকা সকল প্রোডাক্টের পরিমাণের যোগফল
    count = sum(cart.values()) if cart else 0
    return {'cart_count': count}


def update_cart(request):
    if request.method == 'POST':
        cart = request.session.get('cart', {})

        for key, value in request.POST.items():
            if key.startswith('qty_'):
                product_id = key.replace('qty_', '')
                try:
                    new_qty = int(value)
                    if new_qty > 0:
                        cart[product_id] = new_qty
                    else:
                        cart.pop(product_id, None)
                except ValueError:
                    continue

        request.session['cart'] = cart
        request.session.modified = True

    return redirect('cart_view')

def clear_cart(request):
    request.session['cart'] = {}
    return redirect('cart_view')

@login_required
def checkout(request):
    cart = request.session.get('cart', {})

    if not cart and request.method == "GET":
        messages.warning(request, "Your cart is empty!")
        return redirect('product_list')

    if request.method == 'POST':
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        shipping_address = request.POST.get('shipping_address')
        phone = request.POST.get('phone')
        # পেমেন্ট মেথডটি রিসিভ করা হচ্ছে
        payment_method = request.POST.get('payment_method', 'COD')

        # ১. নতুন অর্ডার তৈরি
        order = Order.objects.create(
            user=request.user,
            full_name=full_name,
            email=email,
            address=shipping_address,
            phone=phone,
            payment_method=payment_method, # মডেল আপডেট করার পর এটি কাজ করবে
            total_price=0
        )

        subtotal = 0
        for key, value in cart.items():
            try:
                product = Product.objects.get(id=key)
                qty = value['quantity'] if isinstance(value, dict) else value
                item_total = product.price * qty
                subtotal += item_total

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=qty,
                    price=product.price
                )
            except Product.DoesNotExist:
                continue

        # ২. টোটাল প্রাইজ আপডেট ও সেভ
        order.total_price = subtotal
        order.save()

        # ৩. সেশন ক্লিয়ার করা
        request.session['cart'] = {}
        request.session.modified = True

        messages.success(request, "Order placed successfully!")
        return redirect('order_success_with_id', order_id=order.id)

    # GET লজিক
    cart_items = []
    grand_total = 0
    for key, value in cart.items():
        try:
            product = Product.objects.get(id=key)
            qty = value['quantity'] if isinstance(value, dict) else value
            item_total = product.price * qty
            grand_total += item_total
            cart_items.append({
                'product': product,
                'quantity': qty,
                'total_price': item_total,
            })
        except Product.DoesNotExist:
            continue

    context = {
        'cart_items': cart_items,
        'subtotal': grand_total,
        'grand_total': grand_total,
    }
    return render(request, 'shop/checkout.html', context)


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    user_order_count = Order.objects.filter(user=request.user).count()

    return render(request, 'shop/order_success.html', {
        'order': order,
        'user_order_count': user_order_count
    })


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
def my_orders(request):
    # 'created_at' এর বদলে 'date_ordered' ব্যবহার করুন
    orders_list = Order.objects.filter(user=request.user).order_by('-date_ordered')

    return render(request, 'shop/order_history.html', {'orders': orders_list})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    items = order.items.all()
    return render(request, 'shop/order_detail.html', {'order': order, 'items': items})

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user)

    # PreOrder টেবিল না থাকলে যেন এরর না দেয়, তাই এটি ট্রাই-ক্যাপচার এর মধ্যে রাখুন
    try:
        preorders = PreOrder.objects.filter(user=request.user)
    except:
        preorders = []  # টেবিল না থাকলে খালি লিস্ট পাঠাবে, সাইট ক্র্যাশ করবে না

    return render(request, 'shop/order_history.html', {
        'orders': orders,
        'preorders': preorders
    })


# shop/views.py
def place_order(request):
    if request.method == 'POST':
        # ... অর্ডার সেভ করার লজিক ...
        # অর্ডার সফল হলে:
        return redirect('order_success') # urls.py এ এই নাম থাকতে হবে

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
    products = Product.objects.filter(category__name__in=['Laptop', 'Laptop & Desktop'])
    return render(request, 'shop/laptop_desktop.html', {'products': products})

def phones_tablets(request):
    products = Product.objects.filter(category__name='Phones & Tablets')
    return render(request, 'shop/phones_tablets.html', {'products': products})

def sound_equipment(request):
    products = Product.objects.filter(category__name='Sound Equipment')
    context = {'products': products}
    return render(request, 'shop/sound_equipment.html', context)


def power_accessories(request):

    products = Product.objects.filter(category__name='Power')

    context = {
        'products': products,
    }
    return render(request, 'shop/power_accessories.html', context)

# shop/views.py
# shop/views.py

def fitness_wearable(request):
    # 'Watch' jodi apnar category-r nam hoy, tobe eita use korun
    # Category name-ti admin panel theke check kore exact namti ekhane din
    products = Product.objects.filter(category__name__icontains='Watch')

    # Jodi category name 'Fitness' hoy, tobe:
    # products = Product.objects.filter(category__name__icontains='Fitness')

    return render(request, 'shop/fitness_wearable.html', {'products': products})


def smart_electronics(request):
    # আপনার অ্যাডমিন প্যানেলে ক্যাটাগরির নাম 'Smart Tech' থাকলে এটি কাজ করবে
    products = Product.objects.filter(category__name='Smart Tech')

    context = {
        'products': products,
    }
    return render(request, 'shop/smart_electronics.html', context)

# Registration View (Register URL এর জন্য)

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful! You can now login.")
            return redirect('login')
    else:
        form = UserCreationForm()
    # এখানে 'shop/signup.html' এর বদলে 'shop/register.html' দিন
    return render(request, 'shop/register.html', {'form': form})

@login_required
def profile_view(request):
    return render(request, 'shop/profile.html')