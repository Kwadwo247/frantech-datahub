web: gunicorn sellbundle.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2
worker: celery -A sellbundle worker -l info --concurrency 2
beat: celery -A sellbundle beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
