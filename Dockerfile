FROM runpod/base:1.0.3-cuda1281-ubuntu2204

WORKDIR /

# Python symlinks (runpod/base has python3.11)
RUN ln -sf $(which python3.11) /usr/local/bin/python && \
    ln -sf $(which python3.11) /usr/local/bin/python3

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch with CUDA (must be before other deps)
RUN pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    torchaudio==2.2.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

# Python dependencies
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Clone SadTalker (code only, models on Network Volume)
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /SadTalker

# Install SadTalker dependencies (torch already installed above)
RUN cd /SadTalker && pip install --no-cache-dir -r requirements.txt || true

# Install runpod SDK
RUN pip install --no-cache-dir runpod

# Verify setup
RUN python --version && python -c "import torch, runpod; print(f'torch={torch.__version__} cuda={torch.cuda.is_available()} runpod={runpod.__version__}')"

# Copy handler
COPY handler.py /handler.py

CMD python -u /handler.py
