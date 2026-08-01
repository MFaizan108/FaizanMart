from .models import Ticket, TicketMessage


def create_ticket(customer, subject, description, priority=Ticket.Priority.MEDIUM):
    ticket = Ticket.objects.create(
        customer=customer, subject=subject, description=description, priority=priority
    )
    TicketMessage.objects.create(ticket=ticket, sender=customer, message=description)
    return ticket


def add_message(ticket, sender, message):
    ticket_message = TicketMessage.objects.create(ticket=ticket, sender=sender, message=message)
    if sender.role == "support_staff" and ticket.status == Ticket.Status.OPEN:
        ticket.status = Ticket.Status.IN_PROGRESS
        ticket.save(update_fields=["status", "updated_at"])
    return ticket_message


def update_status(ticket, status):
    ticket.status = status
    ticket.save(update_fields=["status", "updated_at"])
    return ticket
