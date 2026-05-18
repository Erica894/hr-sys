from django.utils import translation


SUPPORTED = {"zh": "zh-hans", "en": "en"}


def _resolve(header_value: str | None) -> str:
    if not header_value:
        return "zh-hans"
    head = header_value.split(",")[0].strip().lower()
    if head.startswith("en"):
        return "en"
    return "zh-hans"


class LanguageMiddleware:
    """Activate Django translation based on Accept-Language header.

    Frontend sends `zh-hans` or `en`; we map to a Django language code
    and activate it for the request. Falls back to zh-hans.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = _resolve(request.META.get("HTTP_ACCEPT_LANGUAGE"))
        translation.activate(lang)
        request.LANGUAGE_CODE = lang
        try:
            return self.get_response(request)
        finally:
            translation.deactivate()
