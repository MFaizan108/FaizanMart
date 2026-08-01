from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import FAQ, Ticket

User = get_user_model()


class SupportTestBase(APITestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            email="ticketcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )
        self.staff = User.objects.create_user(
            email="supportstaff@example.com", password="S0meStrongPass!", role=User.Role.SUPPORT_STAFF
        )
        self.other_customer = User.objects.create_user(
            email="otherticketcustomer@example.com", password="S0meStrongPass!", role=User.Role.CUSTOMER
        )

    def login(self, email):
        response = self.client.post(
            reverse("accounts_api:login"), {"email": email, "password": "S0meStrongPass!"}
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


class TicketTests(SupportTestBase):
    def test_customer_creates_ticket_and_sees_own_only(self):
        self.login("ticketcustomer@example.com")
        response = self.client.post(
            reverse("support_api:ticket-list"), {"subject": "Help", "description": "It broke"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Ticket.Status.OPEN)
        self.assertEqual(len(response.data["messages"]), 1)

        self.client.credentials()
        self.login("otherticketcustomer@example.com")
        response = self.client.get(reverse("support_api:ticket-list"))
        self.assertEqual(response.data["count"], 0)

    def test_staff_reply_moves_ticket_to_in_progress(self):
        self.login("ticketcustomer@example.com")
        create_response = self.client.post(
            reverse("support_api:ticket-list"), {"subject": "Help", "description": "It broke"}
        )
        ticket_id = create_response.data["id"]
        self.client.credentials()

        self.login("supportstaff@example.com")
        response = self.client.post(
            reverse("support_api:ticket-reply", args=[ticket_id]), {"message": "Looking into it"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Ticket.Status.IN_PROGRESS)
        self.assertEqual(len(response.data["messages"]), 2)

    def test_customer_cannot_set_status(self):
        self.login("ticketcustomer@example.com")
        create_response = self.client.post(
            reverse("support_api:ticket-list"), {"subject": "Help", "description": "It broke"}
        )
        ticket_id = create_response.data["id"]
        response = self.client.post(
            reverse("support_api:ticket-set-status", args=[ticket_id]), {"status": "closed"}
        )
        self.assertEqual(response.status_code, 403)


class FAQTests(SupportTestBase):
    def test_public_sees_only_published(self):
        FAQ.objects.create(question="Q1", answer="A1", is_published=True)
        FAQ.objects.create(question="Q2", answer="A2", is_published=False)
        response = self.client.get(reverse("support_api:faq-list"))
        self.assertEqual(response.data["count"], 1)

    def test_non_staff_cannot_create_faq(self):
        self.login("ticketcustomer@example.com")
        response = self.client.post(reverse("support_api:faq-list"), {"question": "Q", "answer": "A"})
        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_faq(self):
        self.login("supportstaff@example.com")
        response = self.client.post(reverse("support_api:faq-list"), {"question": "Q", "answer": "A"})
        self.assertEqual(response.status_code, 201)
