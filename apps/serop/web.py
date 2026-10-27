from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.core.mixins import CompanyAdminRequiredMixin
from apps.dashboards.service import log_activity
from apps.serop.models import SeropSharedServer
from apps.serop.views import _fernet


class ServersView(CompanyAdminRequiredMixin, View):
    """Owners and admins register the servers projects are hosted on.

    The password is encrypted on the way in and is never rendered again; the
    list only says whether one is stored.
    """

    def get(self, request):
        servers = SeropSharedServer.objects.filter(company=request.company).prefetch_related("products")
        return render(request, "serop/servers.html", {"servers": servers, "values": {}})

    def post(self, request):
        values = {k: (request.POST.get(k) or "").strip() for k in ("name", "host", "username")}
        password = request.POST.get("password") or ""
        missing = [label for label, key in (("name", "name"), ("host", "host"), ("username", "username")) if not values[key]]
        if missing or not password:
            if not password:
                missing.append("password")
            messages.error(request, "Fill in " + ", ".join(missing) + ".")
            servers = SeropSharedServer.objects.filter(company=request.company).prefetch_related("products")
            return render(request, "serop/servers.html", {"servers": servers, "values": values}, status=400)

        server = SeropSharedServer.objects.create(
            company=request.company,
            owner=request.user,
            connection_type="password",
            encrypted_password=_fernet().encrypt(password.encode()).decode(),
            **values,
        )
        log_activity(
            request.company, "server_added", f"Server '{server.name}' added",
            actor=request.user, target_content_type="serop_server", target_object_id=server.pk,
        )
        messages.success(request, f"Server '{server.name}' added.")
        return redirect("serop_web:servers")


class ServerDeleteView(CompanyAdminRequiredMixin, View):
    def post(self, request, pk):
        server = get_object_or_404(SeropSharedServer, pk=pk, company=request.company)
        name = server.name
        server.delete()
        log_activity(
            request.company, "server_removed", f"Server '{name}' removed",
            actor=request.user, target_content_type="serop_server", target_object_id=pk,
        )
        messages.success(request, f"Server '{name}' removed. Projects hosted on it no longer have a server.")
        return redirect("serop_web:servers")
