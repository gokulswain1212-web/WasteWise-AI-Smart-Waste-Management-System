
from app.core.config import get_settings
from app.core.security import verify_password

settings = get_settings()

print("Email configured:", bool(settings.auth_email))
print("Password hash configured:", bool(settings.auth_password_hash))
print("Session secret configured:", bool(settings.secret_key))

if settings.auth_email:
    print("Configured email matches gokulswain@gmail.com:",
          settings.auth_email.strip().casefold()
          == "gokulswain@gmail.com".casefold())

if settings.auth_password_hash:
    try:
        result = verify_password(
            "TEMPORARY_TEST_ONLY",
            settings.auth_password_hash
        )
        print("Password hash format is valid:", result is not None)
    except Exception:
        print("Password hash check: needs further investigation")
