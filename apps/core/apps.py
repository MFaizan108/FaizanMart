from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'apps.core'

    def ready(self):
        from .audit import register_audit

        from apps.accounts.models import User
        from apps.catalog.models import Product
        from apps.coupons.models import Coupon
        from apps.orders.models import Order
        from apps.sitesettings.models import SiteSettings
        from apps.vendors.models import Store

        for model in (Product, Order, Store, Coupon, User, SiteSettings):
            register_audit(model)
