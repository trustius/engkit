# Synthetic fixture. Not a real service.
import os

AUTH_HOST = os.environ.get("AUTH_HOST", "auth.example.test")
APP_HOST = os.environ.get("APP_HOST", "app.example.test")

SESSION_COOKIE_NAME = "sid"
# Changed in 2.4.0: previously read from SESSION_COOKIE_DOMAIN env with default ".example.test"
SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN", AUTH_HOST)
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))  # was 86400
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"

SECRET_KEY = os.environ.get("SECRET_KEY", "PLACEHOLDER_SECRET")
