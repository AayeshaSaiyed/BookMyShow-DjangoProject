from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE','bookmyshow.settings')

app = Celery('bookmyshow')
app.config_from_object('django.conf:settings',namespace='CELERY')
app.autodiscover_tasks()