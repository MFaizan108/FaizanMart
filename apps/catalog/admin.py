from django.contrib import admin

from .models import Brand, Category, Product, ProductImage, ProductSpecification, ProductVariant, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "is_featured", "is_active"]
    list_filter = ["is_featured", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "store", "category", "status", "price", "created_at"]
    list_filter = ["status", "product_type", "category"]
    search_fields = ["name", "sku", "barcode"]
    inlines = [ProductImageInline, ProductVariantInline, ProductSpecificationInline]
