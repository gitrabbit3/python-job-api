from openai import OpenAI
from celery import shared_task
from django.conf import settings
from .models import Job, JobStatus


@shared_task(bind=True)
def process_guideline_ingest(self, event_id):
    """Process job with three-step GPT chain: summary → checklist → diagram"""
    try:
        job = Job.objects.get(event_id=event_id)
        job.set_status(JobStatus.PROCESSING.value)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        summary = generate_guideline_summary(client)
        if summary.startswith("Error"):
            job.set_status(JobStatus.FAILED.value)
            job.error_message = summary
            job.save()
            return f"Job {event_id} failed: {summary}"

        checklist = generate_checklist_from_summary(client, summary)
        if checklist.startswith("Error"):
            job.set_status(JobStatus.FAILED.value)
            job.error_message = checklist
            job.save()
            return f"Job {event_id} failed: {checklist}"

        diagram = generate_mermaid_diagram(client, summary, checklist)
        if diagram.startswith("Error"):
            job.set_status(JobStatus.FAILED.value)
            job.error_message = diagram
            job.save()
            return f"Job {event_id} failed: {diagram}"

        job.summary = summary
        job.checklist = checklist
        job.diagram = diagram
        job.set_status(JobStatus.COMPLETED.value)

        return f"Job {event_id} completed successfully"

    except Job.DoesNotExist:
        return f"Job {event_id} not found"
    except Exception as e:
        try:
            job = Job.objects.get(event_id=event_id)
            job.set_status(JobStatus.FAILED.value)
            job.error_message = str(e)
            job.save()
        except Job.DoesNotExist:
            pass
        return f"Job {event_id} failed: {str(e)}"


def generate_guideline_summary(client):
    """Generate a summary of guidelines using GPT-4o"""
    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions="You are an expert at summarizing guidelines and best practices. Create a concise summary of key guidelines for web development and project management.",
            input="Please provide a comprehensive summary of web development guidelines, include accessibility, security, performance, and deployment practices.",
        )
        return response.output_text
    except Exception as e:
        return f"Error generating summary: {str(e)}"


def generate_checklist_from_summary(client, summary):
    """Generate a checklist based on the summary using GPT-4o"""
    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions="You are an expert at creating actionable checklists. Convert guidelines and summaries into clear, actionable checklist items.",
            input=f"Based on this summary of guidelines:\n\n{summary}\n\nPlease create a comprehensive checklist of actionable items that teams should follow. Format as a numbered list with clear, specific tasks.",
        )
        return response.output_text
    except Exception as e:
        return f"Error generating checklist: {str(e)}"


def generate_mermaid_diagram(client, summary, checklist):
    """Generate a Mermaid diagram based on the summary and checklist"""
    try:
        response = client.responses.create(
            model="gpt-4o",
            instructions="""You are an expert at creating Mermaid diagrams. Generate a flowchart that visualizes the workflow or process described in the summary and checklist.

            IMPORTANT: Return ONLY the raw Mermaid syntax, no markdown formatting, no ```mermaid or ``` blocks.

            Use Mermaid syntax and create a clear, professional diagram that shows:
            - Main process steps
            - Decision points
            - Key activities from the checklist

            Example format:
            flowchart TD
                A[Start] --> B[Process]
                B --> C[End]

            Return ONLY the Mermaid code, no explanations or markdown formatting.""",

            input=f"""Based on this summary and checklist, create a Mermaid flowchart:

                    SUMMARY:
                    {summary}

                    CHECKLIST:
                    {checklist}

                Generate a Mermaid flowchart that visualizes this workflow. Return ONLY the raw Mermaid syntax without any markdown formatting or code blocks.
                IMPORTANT: Return ONLY the raw Mermaid syntax, no markdown formatting, no ```mermaid or ``` blocks.""",
        )

        diagram_code = response.output_text.strip()

        if diagram_code.startswith('```mermaid'):
            diagram_code = diagram_code[10:]
        elif diagram_code.startswith('```'):
            diagram_code = diagram_code[3:]

        if diagram_code.endswith('```'):
            diagram_code = diagram_code[:-3]

        return diagram_code.strip()

    except Exception as e:
        return f"Error generating diagram: {str(e)}"
