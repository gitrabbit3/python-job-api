from django.urls import path
from . import views

urlpatterns = [
    path('jobs/', views.create_job, name='create_job'),
    path('jobs/<uuid:event_id>/', views.get_job_status, name='get_job_status'),
    path('queue/', views.queue_status, name='queue_status'),
]
