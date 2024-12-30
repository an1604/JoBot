#!/bin/bash
echo "Checking if MongoDB is already initialized..."
if [ "$(ls -A /data/db)" ]; then
  echo "Database already initialized, skipping restore."
else
  echo "Restoring MongoDB dump..."
  mongorestore --verbose --db job_database /dump/job_database
  echo "MongoDB dump restored."
fi
