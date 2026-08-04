from django.apps import AppConfig


class CatalogConfig(AppConfig):
    name = 'apps.catalog'

    def ready(self):
        from django.db.models.signals import post_delete, post_save

        from . import cache as catalog_cache
        from .models import Category, Product

        def _invalidate_product(sender, instance, **kwargs):
            catalog_cache.invalidate_product(instance.pk)

        def _invalidate_category_list(sender, instance, **kwargs):
            catalog_cache.invalidate_category_list()

        post_save.connect(
            _invalidate_product, sender=Product, weak=False, dispatch_uid="catalog_cache_invalidate_product_save"
        )
        post_delete.connect(
            _invalidate_product, sender=Product, weak=False, dispatch_uid="catalog_cache_invalidate_product_delete"
        )
        post_save.connect(
            _invalidate_category_list, sender=Category, weak=False,
            dispatch_uid="catalog_cache_invalidate_category_save",
        )
        post_delete.connect(
            _invalidate_category_list, sender=Category, weak=False,
            dispatch_uid="catalog_cache_invalidate_category_delete",
        )
