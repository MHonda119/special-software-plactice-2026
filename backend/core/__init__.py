"""Core Django app package initialization.

Having this file ensures the local 'core' app shadows any similarly named
third-party distribution on sys.path so that Django's default test discovery
(`python manage.py test`) correctly imports 'core.tests'.
"""
