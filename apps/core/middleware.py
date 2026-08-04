import threading

_thread_locals = threading.local()


class CurrentRequestMiddleware:
    """Stashes the in-flight request in a thread-local so model signal handlers (which have
    no direct access to the request) can attribute audit log entries to a user/IP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.request = request
        try:
            return self.get_response(request)
        finally:
            _thread_locals.request = None


def get_current_request():
    return getattr(_thread_locals, "request", None)


def get_current_user():
    request = get_current_request()
    if request is not None and getattr(request, "user", None) and request.user.is_authenticated:
        return request.user
    return None


def get_client_ip():
    request = get_current_request()
    if request is None:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
