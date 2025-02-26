import pdb
import re

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

from agents.Server.db import get_db, jobs_source_dict, delete_jobs_by_source
from agents.job import Job
from traffic_agent.linkedin_traffic_agent import LinkedinTrafficAgent

traffic_agent = LinkedinTrafficAgent()


def clean_job_title(job_title):
    """
    Cleans gibberish and unwanted patterns from job titles.
    Args:
        job_title (str): The original job title.
    Returns:
        str: The cleaned job title.
    """
    if not job_title or len(job_title.strip()) == 0:
        return ""
    job_title = re.sub(r"[^\w\s]{2,}", "", job_title)
    job_title = re.sub(r"^[^\w]+|[^\w]+$", "", job_title)
    job_title = re.sub(r"\s+", " ", job_title)
    job_title = job_title.strip().title()
    return job_title


def create_pdf(jobs, source):
    from urllib.parse import urlparse

    # Set the PDF file name
    pdf_file = f"{source}_jobs_summary.pdf"
    pdf_path = os.path.join("generated_pdfs", pdf_file)

    # Ensure the directory exists
    os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

    # Create a PDF canvas
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    # Add a title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, f"Job Summary for Source: {source}")

    # Start writing job details
    y_position = height - 100
    writed_jobs = {}
    for job in jobs:
        key = f'{job['job_title']}_{job['location']}'
        if not key in writed_jobs.keys():
            writed_jobs[key] = job
            if y_position < 100:  # Check if page is full, leaving space for the footer
                # Add copyright footer before creating a new page
                c.setFont("Helvetica-Oblique", 10)
                c.drawString(50, 50, f"© {source} | Generated by joBot")
                c.showPage()
                c.setFont("Helvetica", 12)
                y_position = height - 50

            # Write job details
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y_position, f"Title: {job['job_title']}")
            y_position -= 20
            c.setFont("Helvetica", 12)
            c.drawString(50, y_position, f"Location: {job['location']}")
            y_position -= 20

            c.drawString(50, y_position, f"Link: {job['source']}")
            y_position -= 40  # Add spacing between jobs

    # Add the copyright footer on the last page
    c.setFont("Helvetica-Oblique", 10)
    c.drawString(50, 50, f"© {source} joBot | Generated by joBot")

    # Save the PDF
    c.save()

    return pdf_path


def paginate(query, page=1, per_page=10, collection=None):
    """
    Paginates a MongoDB query.

    :param query: The MongoDB query (e.g., {"FROM": "linkedin_jobs"})
    :param page: The current page number (1-based)
    :param per_page: The number of items per page
    :param collection: The MongoDB collection to query
    :return: A dictionary with paginated results and metadata
    """
    if collection is None:
        raise ValueError("The 'collection' parameter is required.")

    page = max(1, int(page))
    per_page = max(1, int(per_page))
    total_items = collection.count_documents(query)
    results = collection.find(query).skip((page - 1) * per_page).limit(per_page)
    results_list = list(results)
    metadata = {
        "items": results_list,
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": (total_items + per_page - 1) // per_page,  # Ceiling division
        "has_next": page * per_page < total_items,
        "has_prev": page > 1,
    }

    return metadata


def get_data(source_, page, per_page):
    jobs_collection = get_db()['jobs_collection']
    pagination = paginate({"FROM": source_}, page, per_page, jobs_collection)
    jobs_ = set([Job(**job) for job in pagination["items"]])

    return pagination, jobs_


def worker(source):
    agent = jobs_source_dict[source]()
    jobs_collection = get_db()['jobs_collection']
    delete_jobs_by_source(agent.name, jobs_collection)
    agent.get_jobs()


def connections_worker(max_connections, company_name):
    connections_ = traffic_agent.search_company(company_name.lower(), int(max_connections),
                                                use_temp_profile=True)
