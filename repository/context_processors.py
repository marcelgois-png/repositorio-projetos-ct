from .permissions import is_admin_user, is_team_user


def navigation_permissions(request):
    user = request.user
    return {
        "can_manage_users": is_admin_user(user),
        "can_manage_repository": is_team_user(user),
    }
