FROM runpod/pytorch:2.1.0-py3.10-cuda12.1.0-devel-ubuntu22.04

WORKDIR /

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Clone SadTalker
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /SadTalker

# Install SadTalker's own requirements (ignore errors for already-installed packages)
RUN cd /SadTalker && pip install --no-cache-dir -r requirements.txt || true

# Download pretrained models (baked into image for instant cold-start)
RUN cd /SadTalker && bash scripts/download_models.sh

# Copy handler to root
COPY handler.py /handler.py

CMD ["python3", "-u", "/handler.py"]
