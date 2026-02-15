FROM runpod/base:1.0.3-cuda1281-ubuntu2204

WORKDIR /

# Use python3.11 (SadTalker is NOT compatible with 3.12)
RUN ln -sf $(which python3.11) /usr/local/bin/python && \
    ln -sf $(which python3.11) /usr/local/bin/python3

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# IMPORTANT: use "python -m pip" everywhere (bare "pip" uses python3.12!)
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install PyTorch with CUDA (cp311 wheels)
RUN python -m pip install --no-cache-dir \
    torch==2.2.2+cu121 \
    torchvision==0.17.2+cu121 \
    torchaudio==2.2.2+cu121 \
    --index-url https://download.pytorch.org/whl/cu121

# All dependencies in one shot (pinned for SadTalker compatibility)
COPY requirements.txt /requirements.txt
RUN python -m pip install --no-cache-dir -r /requirements.txt

# Fix basicsr: it imports functional_tensor which was removed in torchvision 0.17
RUN find /usr/local/lib/python3.11 -name "*.py" -path "*/basicsr/*" \
    -exec grep -l "functional_tensor" {} \; \
    | xargs -r sed -i 's/from torchvision.transforms.functional_tensor/from torchvision.transforms.functional/g'

# Clone SadTalker (code only, models on Network Volume)
RUN git clone --depth 1 https://github.com/OpenTalker/SadTalker.git /SadTalker

# Also fix any functional_tensor imports inside SadTalker itself
RUN find /SadTalker -name "*.py" \
    -exec grep -l "functional_tensor" {} \; \
    | xargs -r sed -i 's/from torchvision.transforms.functional_tensor/from torchvision.transforms.functional/g'

# THOROUGH verification — import everything SadTalker uses at runtime
RUN python -c "\
import torch, runpod, safetensors, numpy, scipy, librosa, cv2, kornia; \
import face_alignment, imageio, pydub, yacs, numba, tqdm, joblib; \
from basicsr.utils import img2tensor; \
from basicsr.data.degradations import circular_lowpass_kernel; \
from facexlib.utils.face_restoration_helper import FaceRestoreHelper; \
from gfpgan import GFPGANer; \
print(f'ALL OK: torch={torch.__version__} tv={torchvision.__version__} np={numpy.__version__}'); \
print(f'CUDA build: {torch.version.cuda}'); \
import torchvision; \
" && echo "=== ALL IMPORTS VERIFIED ==="

# Copy handler
COPY handler.py /handler.py

CMD python -u /handler.py
