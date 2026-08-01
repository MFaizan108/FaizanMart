from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.catalog.models import Category, Product
from apps.orders.models import Order, OrderItem
from apps.vendors.models import Store

from .models import Review, WishlistItem

User = get_user_model()


class ReviewsTestBase(APITestCase):
    def setUp(self):
        category = Category.objects.create(name="Toys")
        vendor = User.objects.create_user(
            email="reviewvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        self.store = Store.objects.create(owner=vendor, name="Review Store", status=Store.Status.APPROVED)
        self.vendor = vendor
        self.product = Product.objects.create(
            store=self.store, category=category, name="Toy Car", sku="TOY-1", price="15.00",
            status=Product.Status.PUBLISHED,
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.non_buyer = User.objects.create_user(
            email="nonbuyer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

        order = Order.objects.create(
            customer=self.buyer, store=self.store, status=Order.Status.DELIVERED, payment_method="cod",
            shipping_full_name="B", shipping_phone="0300", shipping_address_line="x", shipping_city="x",
            shipping_country="Pakistan",
        )
        OrderItem.objects.create(
            order=order, product=self.product, product_name=self.product.name, sku=self.product.sku,
            unit_price=self.product.price, quantity=1,
        )

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class ReviewTests(ReviewsTestBase):
    def test_buyer_review_is_verified_purchase(self):
        self.login("buyer@example.com")
        response = self.client.post(
            reverse("reviews_api:review-list"),
            {"product": self.product.id, "rating": 5, "comment": "Great toy"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_verified_purchase"])

    def test_non_buyer_review_is_not_verified(self):
        self.login("nonbuyer@example.com")
        response = self.client.post(
            reverse("reviews_api:review-list"), {"product": self.product.id, "rating": 3}
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["is_verified_purchase"])

    def test_duplicate_review_rejected(self):
        Review.objects.create(product=self.product, customer=self.buyer, rating=4)
        self.login("buyer@example.com")
        response = self.client.post(
            reverse("reviews_api:review-list"), {"product": self.product.id, "rating": 5}
        )
        self.assertEqual(response.status_code, 400)

    def test_vendor_can_reply_to_review_on_own_product(self):
        review = Review.objects.create(product=self.product, customer=self.buyer, rating=5)
        self.login("reviewvendor@example.com")
        response = self.client.post(
            reverse("reviews_api:review-reply", args=[review.id]), {"reply": "Thanks!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["vendor_reply"], "Thanks!")

    def test_other_vendor_cannot_reply(self):
        review = Review.objects.create(product=self.product, customer=self.buyer, rating=5)
        other_vendor = User.objects.create_user(
            email="otherreviewvendor@example.com", password="S0meStrongPass!", role=User.Role.VENDOR
        )
        Store.objects.create(owner=other_vendor, name="Other Store", status=Store.Status.APPROVED)
        self.login("otherreviewvendor@example.com")
        response = self.client.post(
            reverse("reviews_api:review-reply", args=[review.id]), {"reply": "Nope"}
        )
        self.assertEqual(response.status_code, 403)


class WishlistTests(ReviewsTestBase):
    def test_toggle_wishlist_add_and_remove(self):
        self.login("buyer@example.com")
        response = self.client.post(reverse("reviews_api:wishlist-toggle"), {"product": self.product.id})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["added"])
        self.assertEqual(WishlistItem.objects.filter(customer=self.buyer).count(), 1)

        response = self.client.post(reverse("reviews_api:wishlist-toggle"), {"product": self.product.id})
        self.assertFalse(response.data["added"])
        self.assertEqual(WishlistItem.objects.filter(customer=self.buyer).count(), 0)
