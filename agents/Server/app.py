import logging
import os
import pdb
import traceback
from multiprocessing import Process

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from datetime import datetime

from flask import Flask, render_template, request, flash, redirect, jsonify, session, url_for
from flask_bootstrap import Bootstrap

from agents.Server.db import get_db, jobs_source_dict, get_connections_from_db, \
    get_jobs_from_db
from agents.Server.utils import clean_job_title, create_pdf, get_data
from agents.file_manager import file_manager
from agents.job import Job
from bson.objectid import ObjectId
from agents.Server.models.handle_models import delete_jobs_by_source, insert_jobs_from_json_updated, \
    delete_jobs_from_json
from agents.tech_map import Company

from traffic_agent.linkedin_traffic_agent import LinkedinTrafficAgent, Connection
from urllib.parse import urlparse, urljoin, parse_qs, urlencode

app = Flask(__name__)
Bootstrap(app)
app.config["SECRET_KEY"] = "hard to guess string"

traffic_agent = LinkedinTrafficAgent()


@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template("index.html")


@app.route('/delete_jobs', methods=['POST'])
def delete_jobs():
    try:
        source_name = request.form.get('source_name')

        # Deleting the jobs both from the DB and the JSON file_manager.py (making it empty).
        jobs_collection = get_db()['jobs_collection']
        delete_jobs_by_source(source_name, jobs_collection)

        # Delete jobs from JSON file_manager.py too.
        filename = f'{source_name}.json'
        file_path = get_filepath_for_jobs_JSONFILE(filename)
        delete_jobs_from_json(file_path)

        return redirect(request.referrer)
    except Exception as e:
        return jsonify(
            {
                "status": "error",
                "message": "An error occurred while deleting jobs.",
                "Exception": e
            })


@app.route('/linkedin_jobs', methods=['GET', 'POST'])
def linkedin_jobs():
    source_ = "linkedin_jobs"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)
    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template(
        'linkedin_jobs.html',
        jobs=jobs_,
        pagination=pagination,
        source=source_
    )


@app.route('/hiring_cafe_jobs', methods=['GET', 'POST'])
def hiring_cafe_jobs():
    source_ = 'hiring_cafe_jobs'
    insert_jobs_from_json_updated(file_manager.get_jobs_filepath("hiring_cafe_jobs"))
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)
    pagination, jobs_ = get_data(source_, page, per_page)

    return render_template('hiring_cafe_jobs.html', pagination=pagination,
                           source=source_, jobs=jobs_)


@app.route('/nvidia_jobs', methods=['GET', 'POST'])
def nvidia_jobs():
    source_ = "nvidia_jobs"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template(
        'nvidia_jobs.html', jobs=jobs_,
        pagination=pagination,
        source=source_)


@app.route('/tipalti_jobs', methods=['GET'])
def tipalti_jobs():
    source = 'tipalti_jobs'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source, page, per_page)
    return render_template('tipalti_jobs.html',
                           jobs=jobs_, pagination=pagination, source=source)


@app.route('/drushim_jobs', methods=['GET'])
def drushim_jobs():
    source = "drushimIL_jobs"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)
    pagination, jobs_ = get_data(source, page, per_page)

    return render_template('drushim_jobs.html', jobs=jobs_, pagination=pagination,
                           source=source)


@app.route('/logon_jobs', methods=['GET', 'POST'])
def logon_jobs():
    source = "logon_jobs"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source, page, per_page)
    return render_template('logon_jobs.html',
                           jobs=jobs_, pagination=pagination, source=source)


@app.route('/amzn_jobs', methods=['GET'])
def amzn_jobs():
    source_ = "amzn_agent"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template('amzn_jobs.html', jobs=jobs_, pagination=pagination,
                           source=source_)


@app.route('/monday_jobs', methods=['GET'])
def monday_jobs():
    source_ = 'monday_agent'
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template('monday_jobs.html', jobs=jobs_,
                           pagination=pagination, source=source_)


@app.route('/sdeg_jobs', methods=['GET'])
def sdeg_jobs():
    source_ = "sdeg_agent"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)

    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template('sdeg_jobs.html', jobs=jobs_,
                           pagination=pagination, source=source_)


@app.route('/msft_jobs')
def msft_jobs():
    source_ = "MSFT_AGENT"
    # remove_duplications_from_db()

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 13, type=int)
    pagination, jobs_ = get_data(source_, page, per_page)
    return render_template('msft_jobs.html', jobs=jobs_, pagination=pagination,
                           source=source_)


@app.route('/delete_job/<job_id>', methods=['POST'])
def delete_job(job_id):
    # Delete the job from the database
    try:
        pdb.set_trace()
        jobs_collection = get_db()['jobs_collection']
        result = jobs_collection.delete_one({"_id": ObjectId(job_id)})
        if result.deleted_count == 1:
            flash("Job deleted successfully!", "success")
        else:
            flash("Job not found or already deleted.", "warning")
    except Exception as e:
        flash(f"An error occurred while deleting the job: {e}", "danger")
        logging.error(f"Error deleting job with _id {job_id}: {e}")
    # Parse the referrer URL to extract the path and query string
    referrer_url = request.referrer
    parsed_referrer = urlparse(referrer_url)
    # Reconstruct the URL with the query string to preserve pagination
    query_params = parse_qs(parsed_referrer.query)
    base_path = parsed_referrer.path
    reconstructed_url = urljoin(referrer_url, f"{base_path}?{urlencode(query_params, doseq=True)}")

    return redirect(reconstructed_url)


@app.route('/mark_pending/<job_id>', methods=['POST'])
def mark_pending(job_id):
    try:
        # Find the job and move it to the Pending collection
        jobs_collection = get_db()['jobs_collection']
        job = jobs_collection.find_one({"_id": ObjectId(job_id)})
        if job:
            pending_jobs_collection = get_db()['pending_jobs_collection']
            pending_jobs_collection.insert_one(job)
            jobs_collection.delete_one({"_id": ObjectId(job_id)})
            flash("Job marked as pending successfully!", "success")
        else:
            flash("Job not found or already moved.", "warning")
    except Exception as e:
        flash(f"An error occurred while marking the job as pending: {e}", "danger")
        logging.error(f"Error marking job with _id {job_id} as pending: {e}")

    return redirect(request.referrer)


@app.route('/pending_jobs', methods=['GET', 'POST'])
def pending_jobs():
    page = request.args.get('page', 1, type=int)
    # remove_duplications_from_db("pending_jobs_collection")

    per_page = request.args.get('per_page', 13, type=int)

    pending_jobs_collection = get_db()['pending_jobs_collection']
    pagination = paginate({}, page, per_page, pending_jobs_collection)
    pending_jobs = [Job(**job) for job in pagination["items"]]
    return render_template(
        'pending_jobs.html',
        jobs=pending_jobs,
        pagination=pagination
    )


@app.route('/summarize_pending_jobs', methods=['POST'])
def summarize_pending_jobs():
    """Collect, and summarize pending jobs and write it down to a file_manager.py (PDF)."""
    try:
        pending_jobs_collection = get_db()['pending_jobs_collection']
        pending_jobs_ = pending_jobs_collection.find()

        # Collecting all company names
        company_dict = {}
        for job in pending_jobs_:
            comp_name = job.get("company", "N/A")
            if comp_name not in company_dict:
                company_dict[comp_name] = []
            company_dict[comp_name].append(job)

        # Create output directory
        output_dir = os.path.join(os.getcwd(), "pending_jobs_summary")
        os.makedirs(output_dir, exist_ok=True)
        pdf_file_name = os.path.join(output_dir, f"Pending_Jobs_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")

        # Create the PDF
        pdf = canvas.Canvas(pdf_file_name, pagesize=letter)
        pdf.setTitle("Pending Jobs Summary")

        # Title and date
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(72, 750, "Pending Jobs Summary")
        pdf.setFont("Helvetica", 12)
        pdf.drawString(72, 735, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        pdf.line(70, 730, 540, 730)

        y = 710

        # Add section with all company names
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(72, y, "Companies Applied To:")
        y -= 20

        pdf.setFont("Helvetica", 12)
        for comp_name in company_dict.keys():
            pdf.drawString(72, y, f"- {comp_name}")
            y -= 15

            # Check if page overflow occurs
            if y < 50:
                pdf.showPage()
                y = 750
                pdf.setFont("Helvetica", 12)

        # Add jobs details
        y -= 20
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(72, y, "Job Details:")
        y -= 20

        count = 1
        for comp_name, jobs_list in company_dict.items():
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(72, y, f"Company: {comp_name}")
            y -= 20

            for job in jobs_list:
                job_title = job.get("job_title", "N/A")
                if job_title:
                    job_title = clean_job_title(job_title)

                job_description = job.get("description", "N/A")
                job_source = job.get("source", "N/A")

                pdf.setFont("Helvetica", 12)
                pdf.drawString(72, y, f"{count}. {job_title}")
                y -= 20
                pdf.setFont("Helvetica-Oblique", 10)
                pdf.drawString(90, y, f"Description: {job_description}")
                y -= 20
                pdf.setFont("Helvetica", 12)

                if job_source != "N/A":
                    pdf.drawString(90, y, "Source: ")
                    pdf.setFillColorRGB(0, 0, 1)  # Blue color for hyperlink
                    pdf.drawString(140, y, job_source)
                    pdf.linkURL(job_source, (140, y, 540, y + 10), relative=0)
                    pdf.setFillColorRGB(0, 0, 0)  # Reset to default color
                else:
                    pdf.drawString(90, y, "Source: N/A")
                y -= 20
                pdf.setFont("Helvetica", 12)

                # Check if page overflow occurs
                if y < 50:
                    pdf.showPage()
                    y = 750
                    pdf.setFont("Helvetica", 12)

                count += 1

        pdf.save()
        logging.info(f"Pending jobs summary successfully written to {pdf_file_name}")
        return redirect(request.referrer or '/')

    except Exception as e:
        logging.error(f"Error generating PDF summary: {e}")
        return f"Error generating PDF summary: {e}", 500


@app.route('/traffic', methods=['GET'])
def traffic():
    return render_template('traffic.html')


@app.route('/get_connections', methods=['POST'])
def get_connections():
    try:
        company_name = request.form.get('user_input') if request.form.get('user_input') else request.form.get(
            'company_name')
        max_connections = request.form.get('max_connections')
        connections_ = traffic_agent.search_company(company_name.lower(), int(max_connections),
                                                    use_temp_profile=True)
        if connections_:
            return redirect(url_for('company_summary', company_name=company_name))
        return redirect(url_for(request.referrer))
    except:
        return redirect(url_for('traffic'))


@app.route('/company_summary', methods=['GET'])
def company_summary():
    company_name = request.args.get('company_name')
    connections_doc = get_connections_from_db(company_name)
    connections = [
        Connection.from_dict(connection_data)
        for connection_data in connections_doc
    ]
    return render_template("company_summary.html", company_name=company_name, connections=connections)


def worker(source):
    agent = jobs_source_dict[source]()
    jobs_collection = get_db()['jobs_collection']
    delete_jobs_by_source(agent.name, jobs_collection)
    agent.get_jobs()


@app.route('/refresh_jobs', methods=['POST'])
def refresh_jobs():
    try:
        source = request.form.get('source')
        if source not in jobs_source_dict.keys():
            raise ValueError(f"Source '{source}' is invalid or not recognized.")

        agent = jobs_source_dict[source]()  # Initialize agent and clear existing jobs
        jobs_collection = get_db()['jobs_collection']
        delete_jobs_by_source(agent.name, jobs_collection)
        print(f"Deleted all resources from the DB for target: {agent.name}")

        # Start the process
        process = Process(target=worker, args=(source,))
        process.start()

        referrer_url = request.referrer
        return redirect(referrer_url)
    except Exception as e:
        logging.error(f"Error in refreshing jobs: {e}")
        return f"An error occurred while refreshing jobs --> {str(e)}", 500


@app.route('/thread_status/<thread_id>', methods=['GET'])
def get_thread_status(thread_id):
    thread_lock = session['active_threads'][thread_id][1]
    with thread_lock:
        status = session['active_threads'][thread_id][-1]  # The last place in the tuple is the status
    return {"thread_id": thread_id, "status": status}


@app.route('/get_companies', methods=['GET'])
def get_companies():
    try:
        job_section_collection = get_db()['job_section_collection']
        company_names = job_section_collection.distinct("company_name")
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 13, type=int)
        query = {"company_name": {"$in": company_names}}
        pagination = paginate(query, page=page, per_page=per_page, collection=job_section_collection)
        companies = [Company.from_dict(company) for company in pagination["items"]]

        return render_template(
            'companies.html',
            companies=companies,
            pagination=pagination
        )
    except Exception as e:
        print(f"Error fetching sections: {e}")
        return "Error fetching sections", 500


def get_filepath_for_jobs_JSONFILE(jobs_filename):
    """
    Given a filename for a given (existing) jobs JSON file_manager.py, this method
    return the dynamic path to the specific file_manager.py.

    :param jobs_filename:
    :return: source_file_path
    """
    try:
        parent_directory = os.path.dirname(os.getcwd())
        selenium_dir = os.path.join(parent_directory, 'selenium')
        selenuim_dir = os.path.join(parent_directory, 'selenuim')

        # Check which directory exists
        if os.path.isdir(selenuim_dir):
            selenium_dir = selenuim_dir
        elif not os.path.isdir(selenium_dir):
            raise FileNotFoundError(f"Selenium directory not found: {selenium_dir}")
        source_file_path = os.path.join(selenium_dir, 'json_jobs', jobs_filename)

        return source_file_path
    except Exception as e:
        print(f'Exception occur: {e}')
        traceback.print_exc()
        return jsonify({"status": "error",
                        "from": "get_filepath_for_jobs_JSONFILE",
                        "message": e
                        })


@app.route("/summarize_jobs", methods=['POST'])
def summarize_jobs():
    try:
        # Get source from form data
        source = request.form.get('source')
        if not source:
            raise ValueError("Source is required")
        jobs = get_jobs_from_db(source)
        if not jobs:
            raise ValueError("No jobs found for the given source")

        pdf_path = create_pdf(jobs, source)
        save_directory = os.path.join(os.getcwd(), "saved_pdfs")
        os.makedirs(save_directory, exist_ok=True)
        file_path = os.path.join(save_directory, f"{source}_jobs.pdf")
        os.rename(pdf_path, file_path)

        return redirect(request.referrer or '/')

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route('/collect_jobs', methods=['POST'])
def collect_jobs():
    try:
        source = request.form.get('source')
        if source not in jobs_source_dict:
            raise ValueError(f"Invalid source: {source}")
        agent = jobs_source_dict[source]()
        # Dynamically locate the correct directory
        filename = f'{agent.name}.json'
        source_file_path = get_filepath_for_jobs_JSONFILE(filename)

        # Check if the JSON file_manager.py exists
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"JSON file_manager.py for {agent.name} not found: {source_file_path}")

        # Insert jobs into the database
        insert_jobs_from_json_updated(file_path=source_file_path,
                                      collection_name='jobs_collection')
        logging.info(f"Jobs from {source_file_path} inserted into the database.")

    except FileNotFoundError as fnf_error:
        logging.error(f"File not found: {fnf_error}")
        return f"File not found: {fnf_error}", 404
    except ValueError as value_error:
        logging.error(f"Invalid source: {value_error}")
        return f"Invalid source: {value_error}", 400
    except Exception as e:
        logging.error(f"Error in collecting jobs: {e}")
        return f"An error occurred while collecting jobs: {e}", 500

    return redirect(request.referrer or '/')


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
