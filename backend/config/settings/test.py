from .base import *

DATABASES["default"]["NAME"] = "hrsys_test"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
