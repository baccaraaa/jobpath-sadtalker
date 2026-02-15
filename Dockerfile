FROM runpod/pytorch:2.1.0-py3.10-cuda12.1.0-devel-ubuntu22.04

WORKDIR /

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Clone SadTalker (code only, models will be on Network Volume)
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /SadTalker

# Install SadTalker dependencies
RUN cd /SadTalker && pip install --no-cache-dir -r requirements.txt || true

# Verify python is accessible and print path for debugging
RUN which python && python --version

# Copy handler
COPY handler.py /handler.py

# Use shell form so conda PATH is picked up
CMD python -u /handler.py
