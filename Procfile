release: python manage.py migrate && python manage.py populate_initial_data
web: python manage.py migrate && python manage.py populate_initial_data && gunicorn sellbundle.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2
worker: celery -A sellbundle worker -l info --concurrency 2
