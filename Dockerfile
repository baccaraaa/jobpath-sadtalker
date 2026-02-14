FROM runpod/base:0.4.0-cuda12.1.0

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies (before cloning, for Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Clone SadTalker
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /app/SadTalker

# Install SadTalker's own requirements
RUN cd /app/SadTalker && pip install --no-cache-dir -r requirements.txt || true

# Download pretrained models (baked into image for instant cold-start)
RUN cd /app/SadTalker && bash scripts/download_models.sh

# Copy handler
COPY handler.py .

CMD ["python", "-u", "handler.py"]
