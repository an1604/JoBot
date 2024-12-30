import json
import logging
import pdb
import re

from deep_translator import GoogleTranslator


logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s')
exclude_keywords_for_job = [
    "senior",
    "lead",
    "principal",
    "head",
    "chief",
    "consultant",
    "specialist",
    "professor",
    "senior-level",
    "enterprise",
    "solutions",
    "head of",
    "technical leader",
    "team leader",
    "manager",
    "department head",
    "business analyst",
    "senior consultant",
    "fellow"
]
translator = GoogleTranslator(source='iw', target='en')


def translate_if_hebrew(text):
    # Detect if the text contains Hebrew characters using regex
    if isinstance(text, str) and re.search(r'[\u0590-\u05FF]', text):
        return GoogleTranslator(source='iw', target='en').translate(text)
    return text


class Job(object):
    def __init__(self, source: str, job_title: str, company: str, is_hybrid: bool = False,
                 job_element=None, description=None, location=None, experience=None,
                 apply_cv_button=None, FROM=None, _id=None):
        self.is_hybrid = is_hybrid
        self.source = translate_if_hebrew(source)
        self.job_title = translate_if_hebrew(job_title)
        self.company = translate_if_hebrew(company)
        self.description = translate_if_hebrew(description)
        self.location = translate_if_hebrew(location)
        self.experience = translate_if_hebrew(experience)

        if _id:
            self._id = _id
        if job_element:
            self.job_element = job_element
        if apply_cv_button:
            self.apply_cv_button = apply_cv_button
        else:
            self.apply_cv_button = None
        logging.info(f"Initialized Job object: {self.to_dict()}")

    def __eq__(self, other):
        if isinstance(other, Job):
            return (self.job_title, self.company, self.location) == (other.job_title, other.company, other.location)
        return False

    def set_job_element(self, job_element):
        self.job_element = job_element
        logging.debug(f"Set job_element for {self.job_title}: {job_element}")

    def set_apply_cv_button(self, apply_cv_button):
        self.apply_cv_button = apply_cv_button
        logging.debug(f"Set apply_cv_button for {self.job_title}: {apply_cv_button}")

    def to_dict(self):
        """Converts the Job object to a dictionary."""
        return {
            "source": self.source,
            "job_title": self.job_title,
            "company": self.company,
            "description": self.description,
            "location": self.location,
            "experience": self.experience,
            # "apply_cv_button": self.apply_cv_button,
            # "is_hybrid": self.is_hybrid
        }

    def to_json(self):
        """Converts the Job object to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=4)

    @staticmethod
    def from_dict(data: dict):
        """Creates a Job object from a dictionary."""
        return Job(
            source=data.get("source"),
            job_title=data.get("job_title"),
            company=data.get("company"),
            description=data.get("description"),
            location=data.get("location"),
            experience=data.get("experience"),
            is_hybrid=data.get("is_hybrid", False),
            job_element=data.get("job_element"),
            apply_cv_button=data.get("apply_cv_button"),
            FROM=data.get("FROM"),
            _id=data.get("_id"),
        )

    @staticmethod
    def from_json(json_string: str):
        """Creates a Job object from a JSON string."""
        data = json.loads(json_string)
        return Job.from_dict(data)

    def __hash__(self):
        """Generates a hash value based on job title, company, and location."""
        return hash((self.job_title, self.company, self.location))

    @staticmethod
    def save_jobs_to_json(jobs, filename):
        try:
            with open(filename, 'a', encoding='utf-8') as file:
                json.dump([job.to_dict() for job in jobs], file, ensure_ascii=False, indent=4)
            logging.info(f"Saved {len(jobs)} jobs to {filename}.")
        except Exception as e:
            logging.error(f"Error saving jobs to JSON: {e}", exc_info=True)
            raise

    @staticmethod
    def load_jobs_from_json(filename="hiring_cafe_jobs.json"):
        jobs = []
        try:
            with open(filename, "r", encoding="utf-8") as file:
                for line_number, line in enumerate(file, start=1):
                    try:
                        job_data = json.loads(line.strip())  # Parse each line as a JSON object
                        jobs.append(job_data)  # Add to jobs list
                    except json.JSONDecodeError as e:
                        logging.error(f"Error parsing JSON on line {line_number}: {e}")
            logging.info(f"Loaded {len(jobs)} jobs from {filename}")
        except FileNotFoundError:
            logging.error(f"File not found: {filename}")
        except Exception as e:
            logging.error(f"An error occurred while reading the file_manager.py: {e}")
        return jobs

    @staticmethod
    def write_job_to_file(job_element_, jobs_path):
        """
        Writes job data to the file_manager.py in append mode without overriding existing contents.

        Args:
            job_element_ (str or dict): The job data to write (can be a string or a dictionary).
            jobs_path (str): The file_manager.py path where the job data will be written.
        """
        try:
            if isinstance(job_element_, Job):
                job_element_ = job_element_.to_dict()

            if Job.is_valid_job(job_element_):
                with open(jobs_path, 'a', encoding='utf-8') as file:
                    if isinstance(job_element_, dict):
                        file.write(json.dumps(job_element_, ensure_ascii=False) + '\n')
                    else:
                        file.write(str(job_element_) + '\n')
                print(f"Job written to : {jobs_path}")
        except Exception as e:
            print(f"Error writing job to {jobs_path}: {e}")

    @classmethod
    def is_valid_job(cls, job_element_):
        global exclude_keywords_for_job
        job_title = job_element_.get('job_title')
        if not job_title:
            return False
        for title in exclude_keywords_for_job:
            if title in job_title.lower():
                print(f"Job {job_title} is not valid, match with {title}")
                return False
        print(f"Job {job_title} is valid!")
        return True
