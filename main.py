from apps import create_app

app = create_app()
celery = app.celery_app
