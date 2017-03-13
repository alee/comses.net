"""
Django settings for core.comses.net

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

from django_jinja.builtins import DEFAULT_EXTENSIONS

import configparser
import os

# go two levels up for root project directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# base directory is one level above the project directory
BASE_DIR = os.path.dirname(PROJECT_DIR)

DEBUG = True

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# Application definition
WAGTAIL_APPS = [
    'wagtail.wagtailforms',
    'wagtail.wagtailredirects',
    'wagtail.wagtailembeds',
    'wagtail.wagtailsites',
    'wagtail.wagtailusers',
    'wagtail.wagtailsnippets',
    'wagtail.wagtaildocs',
    'wagtail.wagtailimages',
    'wagtail.wagtailsearch',
    'wagtail.wagtailadmin',
    'wagtail.wagtailcore',
    'wagtail.contrib.modeladmin',
    'wagtail.contrib.settings',
    'wagtailmenus',
    'taggit',
    'modelcluster',
    'search',
]

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_extensions',
    'django_jinja',
    'guardian',
    'timezone_field',
    'social_django',
    'rest_framework',
    'rest_framework_swagger',
    'webpack_loader',
]

COMSES_APPS = [
    'library',
    'home',
    'citation',
    'core'
]

INSTALLED_APPS = COMSES_APPS + WAGTAIL_APPS + DJANGO_APPS + THIRD_PARTY_APPS

MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',

    'wagtail.wagtailcore.middleware.SiteMiddleware',
    'wagtail.wagtailredirects.middleware.RedirectMiddleware',
]

AUTHENTICATION_BACKENDS = (
    'social_core.backends.github.GithubOAuth2',
    'django.contrib.auth.backends.ModelBackend',
    'core.backends.ComsesObjectPermissionBackend',
    'guardian.backends.ObjectPermissionBackend'
)

ROOT_URLCONF = 'core.urls'


TEMPLATES = [
    {
        'BACKEND': 'django_jinja.backend.Jinja2',
        'APP_DIRS': True,
        'OPTIONS': {
            'match_extension': None,
            'app_dirname': 'templates-jinja2',
            'newstyle_gettext': True,
            # DEFAULT_EXTENSIONS at https://github.com/niwinz/django-jinja/blob/master/django_jinja/builtins/__init__.py
            "extensions": DEFAULT_EXTENSIONS + [
                "django_jinja.builtins.extensions.DjangoExtraFiltersExtension",
                'wagtail.contrib.settings.jinja2tags.settings',
            ],
            'auto_reload': DEBUG,
            'translation_engine': 'django.utils.translation',
            'context_processors': [
                # FIXME: remove debug context processor in prod
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',

                'wagtail.contrib.settings.context_processors.settings',
                'wagtailmenus.context_processors.wagtailmenus',
            ],
            'autoescape': True,
            'auto_reload': DEBUG,
        }
    },
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',

                'wagtail.contrib.settings.context_processors.settings',
                'wagtailmenus.context_processors.wagtailmenus',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# make tags case insensitive
TAGGIT_CASE_INSENSITIVE = True

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

config = configparser.ConfigParser()
config.read('/secrets/config.ini')

SECRET_KEY = config.get('secrets', 'SECRET_KEY')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config.get('database', 'DB_NAME'),
        'USER': config.get('database', 'DB_USER'),
        'PASSWORD': config.get('database', 'DB_PASSWORD'),
        'HOST': config.get('database', 'DB_HOST'),
        'PORT': config.get('database', 'DB_PORT'),
    }
}

LOG_DIRECTORY = config.get('logging', 'LOG_DIRECTORY', fallback=os.path.join(BASE_DIR, 'logs'))
LIBRARY_ROOT = config.get('storage', 'LIBRARY_ROOT', fallback=os.path.join(BASE_DIR, 'library'))
REPOSITORY_ROOT = config.get('storage', 'REPOSITORY_ROOT', fallback=os.path.join(BASE_DIR, 'repository'))

for d in (LOG_DIRECTORY, LIBRARY_ROOT, REPOSITORY_ROOT):
    try:
        if not os.path.isdir(d):
            os.mkdir(d)
    except OSError:
        print("Unable to create directory", d)

# logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'root': {
        'level': 'DEBUG',
        'handlers': ['rollingfile', 'console'],
    },
    'formatters': {
        'verbose': {
            'format': '%(asctime)s %(levelname)-7s %(name)s:%(funcName)s:%(lineno)d %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': "%(levelname)-8s %(message)s"
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'formatter': 'verbose'
        },
        'rollingfile': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(LOG_DIRECTORY, 'comsesnet.log'),
            'backupCount': 6,
            'maxBytes': 10000000,
        },
    },
    'loggers': {
        'home': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False
        },
        'library': {
            'level': 'DEBUG',
            'handlers': ['console', 'rollingfile'],
            'propagate': False,
        },
        'drupal_migrator': {
            'level': 'DEBUG',
            'handlers': ['console', 'rollingfile'],
            'propagate': False,
        }
    }
}

# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

WEBPACK_DIR = '/webpack'

STATICFILES_DIRS = [
    WEBPACK_DIR
]

STATIC_ROOT = '/static'
STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Wagtail settings

WAGTAIL_SITE_NAME = "CoMSES Network"
APPEND_SLASH = True
WAGTAIL_APPEND_SLASH = True

WEBPACK_LOADER = {
    'DEFAULT': {
        'BUNDLE_DIR_NAME': 'assets/',
        'STATS_FILE': os.path.join(WEBPACK_DIR, 'webpack-stats.json'),
    }
}

# Base URL to use when referring to full URLs within the Wagtail admin backend -
# e.g. in notification emails. Don't include '/admin' or a trailing slash
BASE_URL = 'https://www.comses.net'

WAGTAILMENUS_DEFAULT_MAIN_MENU_TEMPLATE = 'home/includes/menu.html'

# authentication settings
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'
WAGTAIL_FRONTEND_LOGIN_URL = 'auth_login'


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ('core.permissions.ComsesPermissions',),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'core.renderers.RootContextHTMLRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
    ),
    'PAGE_SIZE': 10
}

# SSO, user registration, and social auth configuration


# django-registration settings https://django-registration.readthedocs.io/en/2.2/settings.html
ACCOUNT_ACTIVATION_DAYS = 120  # number of days an account has to activate
REGISTRATION_OPEN = True
# apparently does not need to be secret, see
# https://django-registration.readthedocs.io/en/2.2/hmac.html#security-considerations
REGISTRATION_SALT = 'rj9_!qbnz#bcm__w-xo8htm+!y2dd8!!g&qgpwd*omfed!lxnw'


SOCIAL_AUTH_URL_NAMESPACE = 'socialauth'
DISCOURSE_BASE_URL = 'https://forum.comses.net'
DISCOURSE_SSO_SECRET = config.get('secrets', 'DISCOURSE_SSO_SECRET')
