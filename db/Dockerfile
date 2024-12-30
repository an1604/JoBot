FROM mongo:5.0

# Copy the dump data into the container
COPY ./dump /dump

# Add a script to restore the database
COPY ./restore.sh /docker-entrypoint-initdb.d/restore.sh

# Make the script executable
RUN chmod +x /docker-entrypoint-initdb.d/restore.sh
