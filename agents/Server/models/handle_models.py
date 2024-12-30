import logging
import pdb
import traceback

import json
import os

from agents.Server.db import get_db


def insert_jobs_from_json_updated(file_path, collection_name='jobs_collection'):
    try:
        db = get_db()
        collection = db[collection_name]
        with open(file_path, 'r', encoding='utf-8') as file:
            first_line = file.readline().strip()
            if first_line.startswith("{"):
                file.seek(0)  # Reset to beginning of file_manager.py
                jobs = [json.loads(line) for line in file if line.strip()]
            else:
                file.seek(0)
                jobs = json.load(file)
            if isinstance(jobs, list):
                source_name = os.path.basename(file_path).replace('.json', '')
                for job in jobs:
                    job["FROM"] = source_name
                result = collection.insert_many(jobs)
                print(f"{len(result.inserted_ids)} jobs successfully inserted from {source_name}!")
            else:
                print("The JSON file_manager.py must contain a list of job objects.")
    except Exception as e:
        print(f"Error inserting jobs from {file_path}: {e}")


def delete_jobs_by_source(source_value, jobs_collection):
    try:
        if not source_value:
            raise ValueError("Source value is None or invalid.")

        filter_query = {"FROM": source_value}
        result = jobs_collection.delete_many(filter_query)
        return result.deleted_count
    except Exception as e:
        print(f"Error in delete_jobs_by_source: {e}")
        traceback.print_exc()
        raise


def delete_jobs_from_json(file_path):
    try:
        with open(file_path, 'wb') as file:
            pass
        return True
    except:
        return False


def store_sections_in_job_section(directory_path, job_section_collection):
    try:
        # Iterate over JSON files in the directory
        for filename in os.listdir(directory_path):
            if filename.endswith('.json'):
                file_path = os.path.join(directory_path, filename)

                # Open and parse the JSON file_manager.py
                with open(file_path, 'r', encoding='utf-8') as file:
                    json_data = json.load(file)

                # Insert the JSON object into the `job_section` collection
                job_section_collection.insert_one(json_data)
                print(f"Inserted data from {filename} into the job_section collection.")

        print("All sections have been stored in the job_section collection.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == '__main__':
    insert_jobs_from_json_updated(
        r'C:\Users\אביב\PycharmProjects\jobFinder\agents\selenuim\json_jobs\monday_agent.json')
