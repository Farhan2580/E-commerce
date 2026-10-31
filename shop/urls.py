from django.urls import path
from . import views
from . import support_views
from . import payment_views
from . import commerce_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('pc-builder/', commerce_views.pc_builder, name='pc_builder'),
    path('delivery/quote/', commerce_views.delivery_quote, name='delivery_quote'),
    path('product/<int:pk>/question/', commerce_views.ask_question, name='ask_question'),
    path('sitemap.xml', commerce_views.sitemap, name='sitemap'),
    path('robots.txt', commerce_views.robots, name='robots'),
    path('outlets/', support_views.outlets, name='outlets'),
    path('payments/manual/<uuid:attempt_id>/', payment_views.manual_reference, name='manual_payment_reference'),
    path('payments/retry/<uuid:attempt_id>/', payment_views.retry, name='payment_retry'),
    path('payments/start/<uuid:attempt_id>/', payment_views.start, name='payment_start'),
    path('payments/return/<uuid:attempt_id>/', payment_views.returned, name='payment_return'),
    path('payments/ipn/<uuid:attempt_id>/', payment_views.ipn, name='payment_ipn'),
    path('payments/refresh/<uuid:attempt_id>/', payment_views.refresh, name='payment_refresh'),
    path('support/language/', support_views.set_support_language, name='support_language'),
    path('track-order/', support_views.track_order, name='track_order'),
    path('track-order/<int:order_id>/', support_views.track_order, name='track_order_detail'),
    path('product/<int:pk>/stock-alert/', views.subscribe_stock, name='subscribe_stock'),
    path('profile/stock-alert/<int:pk>/cancel/', views.unsubscribe_stock, name='unsubscribe_stock'),
    path('cart/coupon/', views.apply_coupon, name='apply_coupon'),
    path('profile/address/<int:pk>/delete/', views.delete_address, name='delete_address'),
    path('compare/', views.compare, name='compare'),
    path('compare/clear/', views.compare_clear, name='compare_clear'),
    path('compare/<int:pk>/toggle/', views.compare_toggle, name='compare_toggle'),
    path('product/<int:pk>/quick-view/', views.quick_view, name='quick_view'),
    path('cart/drawer/', views.cart_drawer, name='cart_drawer'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('wishlist/<int:pk>/toggle/', views.toggle_wishlist, name='toggle_wishlist'),
    path('section/<int:pk>/', views.home_section, name='home_section'),
    path('information/<slug:slug>/', views.policy, name='policy'),
    path('ajax/review/<int:pk>/', views.ajax_submit_review, name='ajax_submit_review'),
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/update/', views.update_cart, name='update_cart'),
    path('remove-from-cart/<int:pk>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear-cart/', views.clear_cart, name='clear_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('ajax/products/', views.ajax_products, name='ajax_products'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order/<int:order_id>/', views.order_detail, name='order_detail'),
    path('offers/', views.offers, name='offers'),
    path('preorder/', views.preorder, name='preorder'),
    path('preorder/thanks/', views.preorder_thanks, name='preorder_thanks'),
    path('order-history/', views.order_history, name='order_history'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success_with_id'),
    path('signup/', views.signup, name='signup'),
    path('register/', views.register_view, name='register'),

    path('login/', auth_views.LoginView.as_view(
        template_name='shop/login.html',
        next_page='home'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('profile/', views.profile_view, name='profile'),

    path('laptop-desktop/', views.laptop_desktop, name='laptop_desktop'),
    path('phones-tablets/', views.phones_tablets, name='phones_tablets'),
    path('sound-equipment/', views.sound_equipment, name='sound_equipment'),
    path('power-accessories/', views.power_accessories, name='power_accessories'),
    path('fitness-wearable/', views.fitness_wearable, name='fitness_wearable'),
    path('smart-electronics/', views.smart_electronics, name='smart_electronics'),

]
