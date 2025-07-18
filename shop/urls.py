from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('products/', views.product_list, name='product_list'),  # ✅ এই লাইন যোগ করো
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:pk>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.cart_view, name='cart_view'),
    path('update-cart/', views.update_cart, name='update_cart'),
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
    path('signup/', views.signup, name='signup'),

    path('login/', auth_views.LoginView.as_view(template_name='shop/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),


path('laptop-desktop/', views.laptop_desktop, name='laptop_desktop'),
path('phones-tablets/', views.phones_tablets, name='phones_tablets'),
path('sound-equipment/', views.sound_equipment, name='sound_equipment'),
path('power-accessories/', views.power_accessories, name='power_accessories'),
path('fitness-wearable/', views.fitness_wearable, name='fitness_wearable'),
path('smart-electronics/', views.smart_electronics, name='smart_electronics'),


]
