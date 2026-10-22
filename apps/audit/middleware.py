"""
audit/middleware.py
Attaches request context (user, IP, user-agent) to the current thread
so audit.services.record() can access it without needing the request object passed around.
"""
import threading

_local = threading.local()


def get_current_request():
    return getattr(_local, 'request', None)


class RequestContextMiddleware:
    """Store request on thread-local so services can reference it without passing it explicitly."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            return self.get_response(request)
        finally:
            _local.request = None
