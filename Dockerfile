FROM runpod/pytorch:1.0.3-cu1290-torch260-ubuntu2204

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

# Make sure python is available
RUN ln -sf $(which python3.11) /usr/local/bin/python && \
    ln -sf $(which python3.11) /usr/local/bin/python3

# Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Clone SadTalker (code only, models will be on Network Volume)
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /SadTalker

# Install SadTalker dependencies
RUN cd /SadTalker && pip install --no-cache-dir -r requirements.txt || true

# Verify python is accessible
RUN which python && python --version && python -c "import torch; print(f'PyTorch {torch.__version__}, CUDA {torch.cuda.is_available()}')"

# Copy handler
COPY handler.py /handler.py

CMD python -u /handler.py
