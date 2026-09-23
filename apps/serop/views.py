from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from cryptography.fernet import Fernet, InvalidToken
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Company, Membership
from apps.serop.authentication import ExternalTokenAuthentication
from apps.serop.models import SeropNotification, SeropSharedServer
from apps.serop.notifications import notify_read, notify_user

User = get_user_model()


def _fernet():
    return Fernet(settings.SHARED_SERVER_ENCRYPTION_KEY)


def _team_json(company, role):
    owner_membership = Membership.objects.filter(company=company, role=Membership.Role.OWNER).first()
    return {
        "id": str(company.pk),
        "name": company.name,
        "ownerId": str(owner_membership.user_id) if owner_membership else "",
        "createdAt": company.created_at.isoformat(),
        "role": role,
    }


def _member_json(membership):
    user = membership.user
    display_name = (f"{user.first_name} {user.last_name}".strip()) or user.username
    return {
        "userId": str(user.pk),
        "role": membership.role,
        "joinedAt": membership.created_at.isoformat(),
        "displayName": display_name,
        "email": user.email or None,
    }


class BaseSeropView(APIView):
    authentication_classes = [ExternalTokenAuthentication]
    permission_classes = [IsAuthenticated]


class TeamsView(BaseSeropView):
    def get(self, request):
        memberships = Membership.objects.filter(user=request.user).select_related("company")
        teams = [_team_json(m.company, m.role) for m in memberships]
        return Response({"ok": True, "teams": teams})

    def post(self, request):
        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"ok": False, "error": "Team name is required."}, status=status.HTTP_400_BAD_REQUEST)

        slug = slugify(name)
        if not slug:
            return Response({"ok": False, "error": "Could not generate a valid slug from this name."}, status=status.HTTP_400_BAD_REQUEST)
        if Company.objects.filter(slug=slug).exists():
            return Response({"ok": False, "error": "A team with a similar name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        company = Company.objects.create(name=name, slug=slug)
        Membership.objects.create(user=request.user, company=company, role=Membership.Role.OWNER)
        return Response({"ok": True, "team": _team_json(company, Membership.Role.OWNER)}, status=status.HTTP_201_CREATED)


class TeamDetailView(BaseSeropView):
    def get(self, request, team_id):
        membership = Membership.objects.filter(user=request.user, company_id=team_id).select_related("company").first()
        if not membership:
            return Response({"ok": False, "error": "Team not found."}, status=status.HTTP_404_NOT_FOUND)

        members = Membership.objects.filter(company=membership.company).select_related("user")
        return Response({
            "ok": True,
            "team": _team_json(membership.company, membership.role),
            "members": [_member_json(m) for m in members],
        })


class TeamInviteView(BaseSeropView):
    def post(self, request, team_id):
        membership = Membership.objects.filter(user=request.user, company_id=team_id).first()
        if not membership:
            return Response({"ok": False, "error": "Team not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.role not in (Membership.Role.OWNER, Membership.Role.ADMIN):
            return Response({"ok": False, "error": "Only team owners/admins can add members."}, status=status.HTTP_403_FORBIDDEN)

        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"ok": False, "error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        invited_user = User.objects.filter(email=email).first()
        if not invited_user:
            return Response({
                "ok": False,
                "error": "No CRM account found for that email. They need a CRM account before they can be added to a team.",
            }, status=status.HTTP_400_BAD_REQUEST)

        _member, created = Membership.objects.get_or_create(
            user=invited_user,
            company=membership.company,
            defaults={"role": Membership.Role.VIEWER},
        )
        if created:
            notify_user(
                invited_user,
                "team_invitation",
                f"Added to {membership.company.name}",
                f"You were added to the \"{membership.company.name}\" team on Serop.",
                {"teamId": str(membership.company_id)},
            )
        return Response({"ok": True})


class InboxView(BaseSeropView):
    def get(self, request):
        notifications = SeropNotification.objects.filter(user=request.user)
        return Response({"ok": True, "notifications": [n.as_json() for n in notifications]})


class InboxReadView(BaseSeropView):
    def post(self, request, notification_id):
        notification = SeropNotification.objects.filter(pk=notification_id, user=request.user).first()
        if not notification:
            return Response({"ok": False, "error": "Notification not found."}, status=status.HTTP_404_NOT_FOUND)
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at"])
            notify_read(request.user, notification.pk)
        return Response({"ok": True})


class SharedServersView(BaseSeropView):
    def get(self, request):
        company_ids = Membership.objects.filter(user=request.user).values_list("company_id", flat=True)
        servers = SeropSharedServer.objects.filter(company_id__in=company_ids)
        return Response({"ok": True, "servers": [s.as_json() for s in servers]})

    def post(self, request):
        team_id = request.data.get("teamId")
        membership = Membership.objects.filter(user=request.user, company_id=team_id).first()
        if not membership:
            return Response({"ok": False, "error": "Team not found."}, status=status.HTTP_400_BAD_REQUEST)

        name = (request.data.get("name") or "").strip()
        host = (request.data.get("host") or "").strip()
        username = (request.data.get("username") or "").strip()
        if not (name and host and username):
            return Response({"ok": False, "error": "name, host, and username are required."}, status=status.HTTP_400_BAD_REQUEST)

        password = request.data.get("password")
        encrypted_password = _fernet().encrypt(password.encode()).decode() if password else None

        server = SeropSharedServer.objects.create(
            company=membership.company,
            owner=request.user,
            name=name,
            host=host,
            username=username,
            connection_type=request.data.get("connectionType") or "password",
            private_key_path=request.data.get("privateKeyPath") or None,
            project_path=request.data.get("projectPath") or None,
            encrypted_password=encrypted_password,
        )
        return Response({"ok": True, "server": server.as_json()}, status=status.HTTP_201_CREATED)


class SharedServerCredentialsView(BaseSeropView):
    def get(self, request, server_id):
        server = SeropSharedServer.objects.filter(pk=server_id).first()
        if not server or not Membership.objects.filter(user=request.user, company=server.company).exists():
            return Response({"ok": False, "error": "Shared server not found."}, status=status.HTTP_404_NOT_FOUND)

        password = None
        if server.encrypted_password:
            try:
                password = _fernet().decrypt(server.encrypted_password.encode()).decode()
            except InvalidToken:
                password = None

        return Response({
            "ok": True,
            "credentials": {
                "id": str(server.pk),
                "name": server.name,
                "host": server.host,
                "username": server.username,
                "connectionType": server.connection_type,
                "privateKeyPath": server.private_key_path,
                "projectPath": server.project_path,
                "password": password,
            },
        })


class SharedServerDetailView(BaseSeropView):
    def delete(self, request, server_id):
        server = SeropSharedServer.objects.filter(pk=server_id).first()
        if not server:
            return Response({"ok": False, "error": "Shared server not found."}, status=status.HTTP_404_NOT_FOUND)

        is_owner = server.owner_id == request.user.id
        is_team_owner = Membership.objects.filter(user=request.user, company=server.company, role=Membership.Role.OWNER).exists()
        if not (is_owner or is_team_owner):
            return Response({"ok": False, "error": "Only the owner or a team owner can remove this shared server."}, status=status.HTTP_403_FORBIDDEN)

        server.delete()
        return Response({"ok": True})
