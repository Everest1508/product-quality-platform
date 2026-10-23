from django.core.paginator import Paginator

PAGE_SIZES = (10, 20, 50, 100)
DEFAULT_PAGE_SIZE = 20


def paginate(request, qs):
    """The requested page of ``qs``, sized by ``?per_page=`` (one of PAGE_SIZES)."""
    size = request.GET.get("per_page", "")
    size = int(size) if size in {str(n) for n in PAGE_SIZES} else DEFAULT_PAGE_SIZE
    return Paginator(qs, size).get_page(request.GET.get("page", 1))
