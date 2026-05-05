from django.core.exceptions import PermissionDenied


ROLE_ADMIN = "admin"
ROLE_TEAM = "team"
ROLE_READER = "reader"


def get_user_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    profile = getattr(user, "repository_profile", None)
    return getattr(profile, "role", ROLE_READER)


def is_admin_user(user):
    return bool(user.is_authenticated and user.is_active and get_user_role(user) == ROLE_ADMIN)


def is_team_user(user):
    return bool(user.is_authenticated and user.is_active and get_user_role(user) in {ROLE_ADMIN, ROLE_TEAM})


def is_authenticated_reader(user):
    return bool(user.is_authenticated and user.is_active)


def require_admin(user):
    if not is_admin_user(user):
        raise PermissionDenied("Apenas administradores podem acessar esta área.")


def require_team(user):
    if not is_team_user(user):
        raise PermissionDenied("Apenas administradores e equipe podem alterar o repositório.")
