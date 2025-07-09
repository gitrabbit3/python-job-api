import uuid
from enum import Enum
from django.db import models
from django.utils import timezone


class JobStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

    @classmethod
    def choices(cls):
        return [(status.value, status.name.title()) for status in cls]

    @classmethod
    def values(cls):
        return [status.value for status in cls]


class Job(models.Model):

    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=JobStatus.choices(), default=JobStatus.PENDING.value)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    summary = models.TextField(blank=True, null=True)
    checklist = models.TextField(blank=True, null=True)
    diagram = models.TextField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'jobs'
        ordering = ['-created_at']

    def __str__(self):
        return f"Job {self.event_id} - {self.status}"

    @property
    def result(self):
        if self.status == JobStatus.COMPLETED.value:
            return {
                'summary': self.summary,
                'checklist': self.checklist,
                'diagram': self.diagram
            }
        elif self.status == JobStatus.FAILED.value:
            return {
                'error': self.error_message
            }
        return None

    def is_pending(self):
        return self.status == JobStatus.PENDING.value

    def is_processing(self):
        return self.status == JobStatus.PROCESSING.value

    def is_completed(self):
        return self.status == JobStatus.COMPLETED.value

    def is_failed(self):
        return self.status == JobStatus.FAILED.value

    def can_transition_to(self, new_status):
        """Check if status transition is valid"""
        valid_transitions = {
            JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
            JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
            JobStatus.COMPLETED.value: [],
            JobStatus.FAILED.value: []
        }
        return new_status in valid_transitions.get(self.status, [])

    def set_status(self, new_status):
        """Safely set status with validation"""
        if self.can_transition_to(new_status):
            self.status = new_status
            self.save()
            return True
        return False
