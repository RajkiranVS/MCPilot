FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    spacy==3.8.3 \
    flask==3.0.3 \
    gunicorn==22.0.0

# Download spaCy English model
RUN python -m spacy download en_core_web_sm

# SageMaker expects inference code at /opt/program
ENV PROGRAM_PATH=/opt/program
WORKDIR $PROGRAM_PATH

# Copy inference server files
COPY predictor.py $PROGRAM_PATH/
COPY serve $PROGRAM_PATH/

# Make serve executable
RUN chmod +x $PROGRAM_PATH/serve

# SageMaker inference port
EXPOSE 8080

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE

ENTRYPOINT ["/opt/program/serve"]