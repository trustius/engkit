# Synthetic fixture. Not a real service.
from . import config, session
from .users import verify_password  # not included in fixture


def login_post(request, response):
    user = request.form.get("username")
    if not verify_password(user, request.form.get("password")):
        response.status = 401
        return "invalid credentials"
    session.create_session(response, user)
    return response.redirect(f"https://{config.APP_HOST}/dashboard")


def dashboard_get(request, response):
    user = session.current_user(request)
    if user is None:
        return response.redirect(f"https://{config.AUTH_HOST}/login?next=/dashboard")
    return f"welcome {user}"
