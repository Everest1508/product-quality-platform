from apps.accounts.models import Company, Membership

NO_WORKSPACE_MESSAGE = (
    "You are not part of any workspace. "
    "If you were removed from a team, ask an owner or admin to add you back."
)


def has_no_workspace(user):
    """A person who belongs to no workspace, on an install that already has some.

    That is someone who was removed from their team (or never added to one):
    they get no way into the app, and no way to open a workspace of their own.
    Company setup is for the first person on an empty install; staff keep it
    too, since Django admin can create a Company anyway. There is no "was
    removed" marker, because "no membership" is what a removal leaves behind
    and the answer for a never-added account is the same: ask an owner.
    """
    if user.is_staff or user.is_superuser or not Company.objects.exists():
        return False
    return not Membership.objects.filter(user=user).exists()
