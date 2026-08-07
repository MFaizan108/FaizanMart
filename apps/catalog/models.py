from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.utils import unique_slugify


class Category(TimeStampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="catalog/categories/", blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Brand(TimeStampedModel):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    logo = models.ImageField(upload_to="catalog/brands/", blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Tag(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name)
        super().save(*args, **kwargs)


class Product(TimeStampedModel):
    class ProductType(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        DIGITAL = "digital", "Digital"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending Review"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"
        ARCHIVED = "archived", "Archived"

    store = models.ForeignKey(
        "vendors.Store", on_delete=models.CASCADE, related_name="products"
    )
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    brand = models.ForeignKey(
        Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    tags = models.ManyToManyField(Tag, related_name="products", blank=True)

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)

    product_type = models.CharField(
        max_length=20, choices=ProductType.choices, default=ProductType.PHYSICAL
    )
    sku = models.CharField(max_length=100, unique=True)
    barcode = models.CharField(max_length=100, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    warranty_info = models.CharField(max_length=255, blank=True)
    digital_file = models.FileField(upload_to="catalog/digital_products/", blank=True, null=True)
    video_url = models.URLField(blank=True)

    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slugify(self, self.name, max_length=220)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="catalog/products/")
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    sku = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=50, blank=True)
    size = models.CharField(max_length=50, blank=True)
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to="catalog/variants/", blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} ({self.color or '-'}/{self.size or '-'})"


class ProductSpecification(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="specifications")
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.key}: {self.value}"
