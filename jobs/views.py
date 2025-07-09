from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.test import override_settings
from .models import Job, JobStatus
from .serializers import JobCreateSerializer, JobDetailSerializer
from .tasks import process_guideline_ingest
import redis
import json


@api_view(['POST'])
def create_job(request):

    serializer = JobCreateSerializer(data={})
    if serializer.is_valid():
        job = serializer.save()

        # Start the async processing
        try:
            if not getattr(settings, 'TESTING', False) and not getattr(settings, 'CELERY_ALWAYS_EAGER', False):
                process_guideline_ingest.delay(str(job.event_id))
        except Exception as e:
            pass

        return Response({
            'event_id': job.event_id
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_job_status(request, event_id):

    try:
        job = get_object_or_404(Job, event_id=event_id)
        serializer = JobDetailSerializer(job)
        return Response(serializer.data)
    except Exception as e:
        return Response({
            'error': 'Job not found'
        }, status=status.HTTP_404_NOT_FOUND)


def queue_status(request):

    try:
        r = redis.Redis.from_url('redis://redis:6379/0')

        queue_length = r.llen('celery')

        recent_jobs = Job.objects.all().order_by('-created_at')[:20]

        # Test Redis connection
        redis_connected = r.ping()

        # Test Celery worker status by checking if any workers are registered
        try:
            from jobapi.celery import app
            inspect = app.control.inspect()
            active_workers = inspect.active()
            registered_workers = inspect.registered()
            worker_count = len(registered_workers) if registered_workers else 0
            celery_connected = worker_count > 0
        except Exception as celery_error:
            celery_connected = False
            worker_count = 0

        queue_stats = {
            'queue_length': queue_length,
            'redis_connected': redis_connected,
            'celery_connected': celery_connected,
            'worker_count': worker_count,
            'total_jobs': Job.objects.count(),
            'pending_jobs': Job.objects.filter(status=JobStatus.PENDING.value).count(),
            'processing_jobs': Job.objects.filter(status=JobStatus.PROCESSING.value).count(),
            'completed_jobs': Job.objects.filter(status=JobStatus.COMPLETED.value).count(),
            'failed_jobs': Job.objects.filter(status=JobStatus.FAILED.value).count(),
        }

        context = {
            'queue_stats': queue_stats,
            'recent_jobs': recent_jobs,
            'redis_connected': redis_connected,
            'celery_connected': celery_connected,
        }

        return render(request, 'jobs/queue_status.html', context)

    except Exception as e:
        context = {
            'error': str(e),
            'queue_stats': {
                'queue_length': 0,
                'redis_connected': False,
                'celery_connected': False,
                'worker_count': 0,
                'total_jobs': Job.objects.count(),
                'pending_jobs': Job.objects.filter(status=JobStatus.PENDING.value).count(),
                'processing_jobs': Job.objects.filter(status=JobStatus.PROCESSING.value).count(),
                'completed_jobs': Job.objects.filter(status=JobStatus.COMPLETED.value).count(),
                'failed_jobs': Job.objects.filter(status=JobStatus.FAILED.value).count(),
            },
            'recent_jobs': Job.objects.all().order_by('-created_at')[:20],
            'redis_connected': False,
            'celery_connected': False,
        }
        return render(request, 'jobs/queue_status.html', context)
