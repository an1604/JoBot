import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from pymongo import MongoClient

from agents.job import Job
from agents.selenuim.agents.amazon_agent import Amzn_agent
from agents.selenuim.agents.drushimIL_selen_agent import DrushimIL_agent
from agents.selenuim.agents.linkdien_selen_agent import Linkedin_agent
from agents.selenuim.agents.logon_agent import Logon_agent
from agents.selenuim.agents.microsoft_agent import MSFT_agent
from agents.selenuim.agents.nvidia import Nvidia_agent
from agents.selenuim.agents.sdeg_agent import SDEG_Agent


def insert_jobs_from_json(file_path, jobs_collection):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            jobs = json.load(file)
            if isinstance(jobs, list):
                source_name = os.path.basename(file_path).replace('.json', '')

                # Add the source field to each job
                for job in jobs:
                    job["FROM"] = source_name

                result = jobs_collection.insert_many(jobs)
                print(f"{len(result.inserted_ids)} jobs successfully inserted from {source_name}!")
            else:
                print("The JSON file_manager.py must contain a list of job objects.")
    except Exception as e:
        print(f"Error inserting jobs from {file_path}: {e}")


def update_gui(app_, jobs_):
    """Thread-safe update of the GUI."""
    for job_ in jobs_:
        app_.add_job(job_)


def process_agent(agent):
    """Wrapper to process an agent and fetch jobs."""
    jobs_ = agent.get_jobs()
    json_filename = f"{agent.name}.json"
    Job.save_jobs_to_json(jobs_, json_filename)
    return agent.name, json_filename, True


def get_all_jobs():
    client = MongoClient('mongodb://localhost:27017/')
    db = client.job_database  # Replace with your database name
    jobs_collection = db.jobs_source
    all_agents = [Nvidia_agent(), Linkedin_agent(), Amzn_agent(), SDEG_Agent(),
                  MSFT_agent()]

    with ThreadPoolExecutor(max_workers=len(all_agents)) as executor:
        future_to_agent = {executor.submit(process_agent, agent): agent for agent in all_agents}
        for future in as_completed(future_to_agent):
            try:
                agent_name, json_filename, res = future.result()
                if res:
                    print(f"Done process {agent_name}")
                    insert_jobs_from_json(json_filename, jobs_collection)
                else:
                    print(f"Problem with process {agent_name}, check this shit out.")
            except Exception as e:
                agent = future_to_agent[future]
                print(f"Error processing agent {agent.name}: {e}")
        return True


if __name__ == '__main__':
    if get_all_jobs():
        print('DONE!')
    else:
        print('There was a problem.')
