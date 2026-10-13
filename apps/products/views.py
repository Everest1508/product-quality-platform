from django.shortcuts import get_object_or_404
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin, CompanyMemberRequiredMixin
from apps.products.access import require_product_access
from apps.products.models import Product
from apps.uiapi.shell import render_shell


class ProductShellView(CompanyMemberRequiredMixin, View):
    """Pages that need no product (the list), served by the React shell."""

    def get(self, request):
        return render_shell(request)


class ProductAdminShellView(CompanyAdminRequiredMixin, View):
    """The create form: owners and admins only, as before."""

    def get(self, request):
        return render_shell(request)


class ProductPageView(CompanyMemberRequiredMixin, View):
    """Detail and API docs: 404 unless the person may open the product."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductEditView(CompanyAdminRequiredMixin, View):
    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductErrorShellView(CompanyMemberRequiredMixin, View):
    """A product's error list and report form, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductErrorDetailView(CompanyMemberRequiredMixin, View):
    """One error of a product, served by the React shell. 404 unless the error belongs to this product."""

    def get(self, request, pk, error_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        get_object_or_404(product.error_groups, pk=error_pk)
        return render_shell(request)


class ProductTicketListView(CompanyMemberRequiredMixin, View):
    """A product's ticket list, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductTicketKanbanView(CompanyMemberRequiredMixin, View):
    """A product's ticket board, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)


class ProductTicketCreateView(CompanyMemberRequiredMixin, View):
    """A product's new-ticket form, served by the React shell."""

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        return render_shell(request)




class ProductTicketDetailView(CompanyMemberRequiredMixin, View):
    """A ticket under its product, served by the React shell. The ticket must belong to that product."""

    def get(self, request, pk, ticket_pk):
        product = get_object_or_404(Product, pk=pk, company=request.company)
        require_product_access(request, product)
        get_object_or_404(product.tickets, pk=ticket_pk)
        return render_shell(request)
