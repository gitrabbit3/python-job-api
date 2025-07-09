import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobapi.settings')

app = Celery('jobapi')

app.conf.update(
    broker_url='redis://redis:6379/0',
    result_backend='redis://redis:6379/0',
    accept_content=['json'],
    task_serializer='json',
    result_serializer='json',
    timezone='UTC',
    broker_transport_options={
        'visibility_timeout': 3600,
    }
)

app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
