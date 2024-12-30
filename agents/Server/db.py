import json
import logging
import os
import pdb

import pymongo
from pymongo import MongoClient
from agents.selenuim.agents.amazon_agent import Amzn_agent
from agents.selenuim.agents.checkpoint_agent import CheckPoint_agent
from agents.selenuim.agents.drushimIL_selen_agent import DrushimIL_agent
from agents.selenuim.agents.intel_agent import IntelAgent
from agents.selenuim.agents.linkdien_selen_agent import Linkedin_agent
from agents.selenuim.agents.logon_agent import Logon_agent
from agents.selenuim.agents.microsoft_agent import MSFT_agent
from agents.selenuim.agents.nvidia import Nvidia_agent
from agents.selenuim.agents.sdeg_agent import SDEG_Agent
from dotenv import load_dotenv

from agents.selenuim.agents.tipalti_jobs import Tipalti_agent

load_dotenv()

# Map between the source from the POST request, to the 'FROM' value in that differentiate objects in the DB
jobs_source_dict = {
    'tipalti_jobs': Tipalti_agent,
    'amzn_agent': Amzn_agent,
    'drushimIL_jobs': DrushimIL_agent,
    'linkedin_jobs': Linkedin_agent,
    'nvidia_jobs': Nvidia_agent,
    'sdeg_agent': SDEG_Agent,
    'MSFT_AGENT': MSFT_agent,
    'checkpoint_jobs': CheckPoint_agent,
    'intel_jobs': IntelAgent,
    'logon_jobs': Logon_agent
}

db_dict = None


def get_db():
    """
    Initializes and retrieves the database and its collections as a dictionary.

    Returns:
        dict: A dictionary containing the MongoDB client, database, and collections.
    """
    global db_dict
    if db_dict is None:
        try:
            host = os.getenv('MONGO_HOST', 'localhost')
            port = os.getenv('MONGO_PORT', '27017')

            client = MongoClient(f'mongodb://{host}:{port}/')
            db = client['job_database']

            db_dict = {
                'client': client,
                'db': db,
                'jobs_collection': db['jobs'],
                'job_section_collection': db['job_section'],
                'pending_jobs_collection': db['pending_jobs'],
                'connections_collection': db['connections']
            }
            return db_dict
        except Exception as e:
            print(f"Exception occurred in get_db: {e}")
            db_dict = None
            return None
    else:
        return db_dict


# def get_db():
#     global db_dict
#     if db_dict is None:
#         try:
#             host = 'localhost'
#             client = MongoClient(f'mongodb://{host}:27017/')
#             db = client['job_database']  # Reference the database by name
#
#             jobs_collection = db['jobs']
#             job_section_collection = db['job_section']
#             pending_jobs_collection = db['pending_jobs']
#
#             # Store the client, database, and collections in a dictionary
#             db_dict = {
#                 'client': client,
#                 'db': db,
#                 'jobs_collection': jobs_collection,
#                 'job_section_collection': job_section_collection,
#                 'pending_jobs_collection': pending_jobs_collection,
#             }
#             return db_dict
#         except Exception as e:
#             print(f"Exception occurred in get_db: {e}")
#             db_dict = None
#             return None
#     else:
#         return db_dict


def add_jobs_from_list(jobs_list, jobs_collection):
    result = jobs_collection.insert_many([job.to_json() for job in jobs_list])
    print(f"{len(result.inserted_ids)} jobs successfully inserted!")
    return result


def insert_jobs_from_json_updated(file_path, collection_name='jobs_collection'):
    db = get_db()
    jobs_collection = db[collection_name]
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            # Determine if the file_manager.py is JSON Lines or JSON Array
            first_line = file.readline().strip()
            if first_line.startswith("{"):
                # JSON Lines: Process line by line
                file.seek(0)  # Reset to the beginning of the file_manager.py
                jobs = [json.loads(line) for line in file if line.strip()]
            else:
                # JSON Array: Parse as a whole
                file.seek(0)
                jobs = json.load(file)

            if isinstance(jobs, list):
                source_name = os.path.basename(file_path).replace('.json', '')

                # Filter jobs to remove duplicates based on 'source' and 'job_title'
                jobs_filtered = []
                seen_jobs = set()  # Track unique jobs by a tuple (source, job_title)

                for job in jobs:
                    job["FROM"] = source_name
                    job_key = (job['source'], job['job_title'])

                    if job_key not in seen_jobs:
                        seen_jobs.add(job_key)
                        jobs_filtered.append(job)

                print(f"After filtering: {len(jobs_filtered)} jobs to be inserted.")

                # Insert filtered jobs into the collection
                if jobs_filtered:
                    result = jobs_collection.insert_many(jobs_filtered)
                    print(f"{len(result.inserted_ids)} jobs successfully inserted from {source_name}!")
                else:
                    print("No new jobs to insert after filtering.")
            else:
                print("The JSON file_manager.py must contain a list of job objects.")
    except Exception as e:
        print(f"Error inserting jobs from {file_path}: {e}")


def delete_jobs_by_source(source_value):
    """
    Deletes all documents from the MongoDB collection where the FROM field matches the given value.

    Args:
        source_value (str): The value of the FROM field to filter and delete documents.

    Returns:
        int: The number of documents deleted.
    """
    try:
        db = get_db()
        jobs_collection = db['jobs_collection']
        filter_query = {"FROM": source_value}
        result = jobs_collection.delete_many(filter_query)
        print(f"Deleted {result.deleted_count} documents where FROM='{source_value}'.")
        return result.deleted_count
    except Exception as e:
        print(f"An error occurred: {e}")
        return 0


def is_relevant_job(job_title):
    """
    Checks if a job title is relevant based on predefined criteria.
    Args:
        job_title (str): The job title to check.

    Returns:
        bool: True if the job is relevant, False otherwise.
    """
    if not job_title:
        return False  # Exclude jobs with no title

    job_title = job_title.lower()
    irrelevant_keywords = [
        "ux/ui", "ux", "ui", "senior", "team leader", "director",
        "architect", "principal", "manager", "lead", "vp", "head of"
    ]
    if any(keyword in job_title for keyword in irrelevant_keywords):
        return False
    relevant_keywords = [
        "junior", "graduate", "entry-level", "software engineer",
        "developer", "intern"
    ]
    return any(keyword in job_title for keyword in relevant_keywords)


def remove_duplications_from_db(collection_name='jobs_collection'):
    """
    Removes duplicate and irrelevant jobs from the database.
    Args:
        collection_name (str): The name of the collection to clean up.
    Returns:
        set: Unique jobs retained in the collection.
    """
    db = get_db()
    if not db:
        print("Failed to connect to the database.")
        return

    jobs_collection = db[collection_name]
    jobs_list = list(jobs_collection.find())

    unique_jobs = set()  # Set to hold unique jobs
    duplicates = []  # List to track duplicate jobs
    irrelevant_jobs = []  # List to track irrelevant jobs for deletion

    # Defining a unique key (a tuple) that can differentiate between jobs in the DB.
    for job in jobs_list:
        job_title = job.get('job_title')
        if is_relevant_job(job_title):
            job_key = (job_title, job.get('location'), job.get('company'), job.get('source'))
            if job_key not in unique_jobs:
                unique_jobs.add(job_key)
            else:
                duplicates.append(job['_id'])
        else:
            irrelevant_jobs.append(job['_id'])

    if duplicates:
        result = jobs_collection.delete_many({'_id': {'$in': duplicates}})
        if result:
            logging.info(f"Finished removing duplicates. Removed {len(duplicates)} duplicate jobs.")

    if irrelevant_jobs:
        result = jobs_collection.delete_many({'_id': {'$in': irrelevant_jobs}})
        if result:
            logging.info(f"Removed {len(irrelevant_jobs)} irrelevant jobs.")

    return unique_jobs


def job_contains_in_db(job):
    try:
        db = get_db()
        if not db:
            print("Failed to connect to the database.")
            return False

        job_data = job.to_json()
        if db['jobs_collection'].find_one(job_data) or db['pending_jobs_collection'].find_one(job_data):
            return True
        return False
    except Exception as e:
        print(f"An error occurred while checking the job in the database: {e}")
        return False


def add_job_to_pending_jobs(job):
    try:
        db = get_db()
        if not db:
            print("Failed to connect to the database.")
            return False
        pending_jobs_collection = db['pending_jobs_collection']
        pending_jobs_collection.insert_one(job.to_dict())
        return True
    except Exception as e:
        print(f"Exception occur in add_job_to_pending_jobs() {e}")
        return False


def add_job_to_job_collection(job):
    try:
        db = get_db()
        if not db:
            print("Failed to connect to the database.")
            return False
        jobs_collection = db['jobs_collection']
        res = jobs_collection.insert_one(job.to_dict())
        print(f"Job {job.job_title} added to the database.")
        print(f"Job ID: {res.inserted_id}")
        return True
    except Exception as e:
        print(f"Exception occur in add_job_to_job_collection() {e}")
        return False


def get_connections_from_db(company_name):
    db = get_db()
    connections_collection = db['connections_collection']
    connection_doc = connections_collection.find_one({'company_name': company_name.lower()})
    if connection_doc and 'connections' in connection_doc:
        return connection_doc['connections']
    else:
        return []


def get_jobs_from_db(jobs_source):
    db = get_db()
    jobs_collection = db['jobs_collection']
    jobs_cursor = jobs_collection.find({'FROM': jobs_source})

    jobs = list(jobs_cursor)
    return jobs


def add_connection(collection_name, connection):
    db = get_db()
    collection = db[collection_name]
    try:
        # Check and insert or update the document
        collection.update_one(
            {"company_name": connection.company_name},  # Find document with this company_name
            {"$set": connection.to_dict()},  # Update with the new data
            upsert=True  # Insert if not found
        )
        return True
    except pymongo.errors.DuplicateKeyError as e:
        print(f"Duplicate entry: {e}")
        return False


def connection_in_db(connection):
    db = get_db()
    connections_collection = db['connections_collection']
    if connections_collection.find_one(connection.to_dict()):
        return True
    add_connection("connections_collection", connection)
    return False


def drop_connection_from_db(connection):
    db = get_db()
    connections_collection = db['connections_collection']
    connections_collection.delete_one(connection.to_json())
