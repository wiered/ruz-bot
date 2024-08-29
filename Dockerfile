# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

# Set port to 5000
EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Generating db.csv
FROM alpine as builder
RUN echo "id,group_id,group_name" > /tmp/db.csv

# Copying db.csv
FROM ruz-bot
COPY --from=builder /tmp/db.csv /db/db.csv

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["python", "main.py"]
