from django.conf import settings
from django.db import models


class ProductView(models.Model):
    product = models.ForeignKey("catalog.Product", on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="product_views"
    )
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [models.Index(fields=["product", "viewed_at"]), models.Index(fields=["user", "viewed_at"])]

    def __str__(self):
        return f"{self.user or 'guest'} viewed {self.product.name}"
