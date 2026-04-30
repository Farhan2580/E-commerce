from django.contrib import admin
from .models import Category, Product, Order, OrderItem, Review, Offer
from .models import Preorder

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'category')
    fields = ('name', 'description', 'price', 'category', 'image',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    # অ্যাডমিন প্যানেলে কোন কোন কলাম দেখা যাবে
    list_display = ('id', 'user', 'full_name', 'total_price', 'date_ordered')

    # ডানপাশে ফিল্টার করার অপশন
    list_filter = ('date_ordered', 'user')

    # সার্চ করার অপশন
    search_fields = ('full_name', 'phone', 'email')

    # অর্ডারের ভেতরে ঢুকলে যা যা এডিট করা যাবে (সব রিড-অনলি রাখতে চাইলে readonly_fields ব্যবহার করুন)
    readonly_fields = ('date_ordered',)

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price')

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'product__name', 'comment')

@admin.register(Offer)
class OfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')

class PreOrderAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'product_info', 'created_at')
    readonly_fields = ('created_at',)



admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Preorder)