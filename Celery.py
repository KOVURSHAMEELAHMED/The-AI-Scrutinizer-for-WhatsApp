import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fake_news_detector.settings')

app = Celery('fake_news_detector')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()