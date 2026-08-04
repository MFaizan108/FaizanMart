import stripe as stripe_sdk
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .services import easypaisa as easypaisa_gateway
from .services import jazzcash as jazzcash_gateway
from .services import stripe as stripe_gateway


@csrf_exempt
@require_POST
def stripe_webhook(request):
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = stripe_gateway.construct_webhook_event(request.body, sig_header)
    except ValueError:
        return HttpResponseBadRequest("Invalid payload.")
    except stripe_sdk.error.SignatureVerificationError:
        return HttpResponseBadRequest("Invalid signature.")

    stripe_gateway.handle_webhook_event(event)
    return HttpResponse(status=200)


@csrf_exempt
@require_POST
def jazzcash_callback(request):
    try:
        orders = jazzcash_gateway.handle_callback(request.POST.dict())
    except ValueError:
        return HttpResponseBadRequest("Invalid signature.")
    if not orders:
        return HttpResponse("Unknown or already-processed transaction.", status=200)
    return HttpResponse(f"Payment {orders[0].payment_status} for order {orders[0].order_number}.")


@csrf_exempt
@require_POST
def easypaisa_callback(request):
    try:
        orders = easypaisa_gateway.handle_callback(request.POST.dict())
    except ValueError:
        return HttpResponseBadRequest("Invalid signature.")
    if not orders:
        return HttpResponse("Unknown or already-processed transaction.", status=200)
    return HttpResponse(f"Payment {orders[0].payment_status} for order {orders[0].order_number}.")
