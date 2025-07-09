import uuid
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import Job, JobStatus
from .tasks import process_guideline_ingest, generate_guideline_summary, generate_checklist_from_summary, generate_mermaid_diagram


class JobModelTest(TestCase):
    """Test cases for the Job model."""

    def test_job_creation(self):
        """Test that a job can be created with default values."""
        job = Job.objects.create()
        self.assertIsNotNone(job.event_id)
        self.assertEqual(job.status, JobStatus.PENDING.value)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)

    def test_job_str_representation(self):
        """Test the string representation of a job."""
        job = Job.objects.create()
        expected = f"Job {job.event_id} - pending"
        self.assertEqual(str(job), expected)

    def test_job_result_property_pending(self):
        """Test result property for pending job."""
        job = Job.objects.create(status=JobStatus.PENDING.value)
        self.assertIsNone(job.result)

    def test_job_result_property_completed(self):
        """Test result property for completed job."""
        job = Job.objects.create(
            status=JobStatus.COMPLETED.value,
            summary='Test summary',
            checklist='Test checklist',
            diagram='flowchart TD A[Start] --> B[End]'
        )
        expected = {
            'summary': 'Test summary',
            'checklist': 'Test checklist',
            'diagram': 'flowchart TD A[Start] --> B[End]'
        }
        self.assertEqual(job.result, expected)

    def test_job_result_property_failed(self):
        """Test result property for failed job."""
        job = Job.objects.create(
            status=JobStatus.FAILED.value,
            error_message='Test error'
        )
        expected = {'error': 'Test error'}
        self.assertEqual(job.result, expected)


class JobAPITest(APITestCase):
    """Test cases for the Job API endpoints."""

    def test_create_job(self):
        """Test creating a new job via API."""
        url = reverse('create_job')
        response = self.client.post(url, {})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('event_id', response.data)

        # Verify job was created in database
        job = Job.objects.get(event_id=response.data['event_id'])
        self.assertEqual(job.status, JobStatus.PENDING.value)

    @patch('jobs.views.process_guideline_ingest.delay')
    def test_create_job_triggers_task(self, mock_delay):
        """Test that creating a job triggers the Celery task."""
        # Mock the settings to allow task queuing in test
        with override_settings(TESTING=False, CELERY_ALWAYS_EAGER=False):
            url = reverse('create_job')
            response = self.client.post(url, {})

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            # Verify the task was called with the correct event_id
            job = Job.objects.get(event_id=response.data['event_id'])
            mock_delay.assert_called_with(str(job.event_id))

    def test_get_job_status_pending(self):
        """Test getting status of a pending job."""
        job = Job.objects.create()
        url = reverse('get_job_status', kwargs={'event_id': job.event_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['event_id'], str(job.event_id))
        self.assertEqual(response.data['status'], JobStatus.PENDING.value)
        self.assertIsNone(response.data['result'])

    def test_get_job_status_completed(self):
        """Test getting status of a completed job."""
        job = Job.objects.create(
            status=JobStatus.COMPLETED.value,
            summary='Test summary',
            checklist='Test checklist',
            diagram='flowchart TD A[Start] --> B[End]'
        )
        url = reverse('get_job_status', kwargs={'event_id': job.event_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], JobStatus.COMPLETED.value)
        self.assertIsNotNone(response.data['result'])
        self.assertEqual(response.data['result']['summary'], 'Test summary')
        self.assertEqual(response.data['result']['checklist'], 'Test checklist')
        self.assertEqual(response.data['result']['diagram'], 'flowchart TD A[Start] --> B[End]')

    def test_get_job_status_failed(self):
        """Test getting status of a failed job."""
        job = Job.objects.create(
            status=JobStatus.FAILED.value,
            error_message='Test error'
        )
        url = reverse('get_job_status', kwargs={'event_id': job.event_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], JobStatus.FAILED.value)
        self.assertIsNotNone(response.data['result'])
        self.assertEqual(response.data['result']['error'], 'Test error')

    def test_get_nonexistent_job(self):
        """Test getting status of a job that doesn't exist."""
        fake_event_id = uuid.uuid4()
        url = reverse('get_job_status', kwargs={'event_id': fake_event_id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)


class JobTasksTest(TestCase):
    """Test cases for the Celery tasks."""

    @patch('openai.OpenAI')
    def test_process_guideline_ingest_success(self, mock_openai):
        """Test successful processing of a guideline-ingest job."""
        # Mock OpenAI responses
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.output_text = "Test summary"
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create a job
        job = Job.objects.create()
        event_id = str(job.event_id)

        # Process the job
        result = process_guideline_ingest(event_id)

        # Verify the job was updated
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED.value)
        self.assertIsNotNone(job.summary)
        self.assertIsNotNone(job.checklist)
        self.assertIsNotNone(job.diagram)
        self.assertEqual(result, f"Job {event_id} completed successfully")

    @patch('jobs.tasks.generate_guideline_summary')
    def test_process_guideline_ingest_failure(self, mock_summary):
        """Test handling of task failure."""
        # Mock the summary function to return an error
        mock_summary.return_value = "Error generating summary: Test error"

        # Create a job
        job = Job.objects.create()
        event_id = str(job.event_id)

        # Process the job (will fail due to summary error)
        result = process_guideline_ingest(event_id)

        # Verify the job was marked as failed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED.value)
        self.assertIsNotNone(job.error_message)
        self.assertIn("failed", result)

    def test_process_guideline_ingest_nonexistent_job(self):
        """Test processing a job that doesn't exist."""
        fake_event_id = str(uuid.uuid4())
        result = process_guideline_ingest(fake_event_id)
        self.assertIn("not found", result)

    @patch('openai.OpenAI')
    def test_generate_guideline_summary(self, mock_openai):
        """Test the guideline summary generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.output_text = "Test summary content"
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        summary = generate_guideline_summary(mock_client)

        self.assertEqual(summary, "Test summary content")
        mock_client.responses.create.assert_called_once()

    @patch('openai.OpenAI')
    def test_generate_checklist_from_summary(self, mock_openai):
        """Test the checklist generation from summary."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.output_text = "1. Test checklist item"
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        checklist = generate_checklist_from_summary(mock_client, "Test summary")

        self.assertEqual(checklist, "1. Test checklist item")
        mock_client.responses.create.assert_called_once()

    @patch('openai.OpenAI')
    def test_generate_mermaid_diagram(self, mock_openai):
        """Test the Mermaid diagram generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.output_text = "flowchart TD A[Start] --> B[End]"
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        diagram = generate_mermaid_diagram(mock_client, "Test summary", "Test checklist")

        self.assertEqual(diagram, "flowchart TD A[Start] --> B[End]")
        mock_client.responses.create.assert_called_once()

    def test_job_status_methods(self):
        """Test the job status helper methods."""
        job = Job.objects.create()

        self.assertTrue(job.is_pending())
        self.assertFalse(job.is_processing())
        self.assertFalse(job.is_completed())
        self.assertFalse(job.is_failed())

        job.set_status(JobStatus.PROCESSING.value)
        self.assertFalse(job.is_pending())
        self.assertTrue(job.is_processing())

        job.set_status(JobStatus.COMPLETED.value)
        self.assertTrue(job.is_completed())

    def test_job_status_transitions(self):
        """Test job status transition validation."""
        job = Job.objects.create()

        # Valid transitions
        self.assertTrue(job.can_transition_to(JobStatus.PROCESSING.value))
        self.assertTrue(job.can_transition_to(JobStatus.FAILED.value))

        # Invalid transitions
        self.assertFalse(job.can_transition_to(JobStatus.COMPLETED.value))

        # Test set_status with valid transition
        self.assertTrue(job.set_status(JobStatus.PROCESSING.value))
        self.assertEqual(job.status, JobStatus.PROCESSING.value)

        # Test set_status with invalid transition
        job = Job.objects.create()
        self.assertFalse(job.set_status(JobStatus.COMPLETED.value))
        self.assertEqual(job.status, JobStatus.PENDING.value)
