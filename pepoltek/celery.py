"""
Celery application - defines queues and task routing.
Queues: ai | files | notify | default
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pepoltek.settings.dev')

app = Celery('pepoltek')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ─── Queue Declarations ───────────────────────────────────────────────────────
# Workers should be started per queue:
#   celery -A pepoltek worker -Q ai --concurrency 2 -n worker-ai@%h
#   celery -A pepoltek worker -Q files --concurrency 4 -n worker-files@%h
#   celery -A pepoltek worker -Q notify --concurrency 8 -n worker-notify@%h
#   celery -A pepoltek worker -Q default --concurrency 4 -n worker-default@%h
#   celery -A pepoltek beat --scheduler django_celery_beat.schedulers:DatabaseScheduler

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
