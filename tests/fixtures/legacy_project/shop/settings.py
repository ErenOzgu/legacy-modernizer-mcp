import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

DEBUG = True
TEMPLATE_DEBUG = True

TEMPLATE_DIRS = (os.path.join(BASE_DIR, "templates"),)

TEMPLATE_CONTEXT_PROCESSORS = (
    "django.core.context_processors.request",
    "django.contrib.auth.context_processors.auth",
)

INSTALLED_APPS = (
    "django.contrib.admin",
    "django.contrib.auth",
    "south",
    "shop",
)

MIDDLEWARE_CLASSES = (
    "django.middleware.common.CommonMiddleware",
)

ROOT_URLCONF = "shop.urls"
