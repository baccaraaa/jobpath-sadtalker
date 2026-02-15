"""
RunPod Serverless handler for SadTalker lip-sync.
Models are stored on Network Volume (/runpod-volume) for fast cold starts.
"""
import base64
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import runpod

print(f"[INFO] Python: {sys.executable} {sys.version}", flush=True)
print(f"[INFO] runpod version: {runpod.__version__}", flush=True)

# Network Volume mount point (RunPod mounts it here)
VOLUME_PATH = Path("/runpod-volume")
MODELS_DIR = VOLUME_PATH / "sadtalker-models"
SADTALKER_DIR = Path("/SadTalker")

# Model URLs (from SadTalker's download script)
MODEL_URLS = {
    "checkpoints": {
        "epoch_20.pth": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/epoch_20.pth",
        "auido2exp_00300-model.pth": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/auido2exp_00300-model.pth",
        "auido2pose_00140-model.pth": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/auido2pose_00140-model.pth",
        "mapping_00109-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00109-model.pth.tar",
        "mapping_00229-model.pth.tar": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/mapping_00229-model.pth.tar",
        "SadTalker_V0.0.2_256.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_256.safetensors",
        "SadTalker_V0.0.2_512.safetensors": "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/SadTalker_V0.0.2_512.safetensors",
    },
    "gfpgan/weights": {
        "alignment_WFLW_4HG.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth",
        "detection_Resnet50_Final.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",
        "GFPGANv1.4.pth": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
        "parsing_parsenet.pth": "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth",
    },
}


def ensure_models():
    """Download models to Network Volume if they don't exist yet."""
    if not VOLUME_PATH.exists():
        print("[WARN] Network Volume not mounted at /runpod-volume!", flush=True)
        print("[WARN] Falling back to local storage (models won't persist)", flush=True)

    for subdir, files in MODEL_URLS.items():
        target_dir = MODELS_DIR / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename, url in files.items():
            filepath = target_dir / filename
            if filepath.exists() and filepath.stat().st_size > 1000:
                continue
            print(f"[DOWNLOAD] {filename}...", flush=True)
            subprocess.run(
                ["curl", "-L", "-s", "-o", str(filepath), url],
                check=True,
                timeout=300,
            )
            print(f"[DOWNLOAD] {filename} done ({filepath.stat().st_size / 1e6:.1f} MB)", flush=True)

    # Symlink models into SadTalker directory
    st_checkpoints = SADTALKER_DIR / "checkpoints"
    st_gfpgan = SADTALKER_DIR / "gfpgan"

    # Remove existing dirs/symlinks and create new symlinks
    for link_path, target in [
        (st_checkpoints, MODELS_DIR / "checkpoints"),
        (st_gfpgan, MODELS_DIR / "gfpgan"),
    ]:
        if link_path.is_symlink():
            link_path.unlink()
        elif link_path.is_dir():
            import shutil
            shutil.rmtree(link_path)
        if target.exists():
            link_path.symlink_to(target)
            print(f"[LINK] {link_path} -> {target}", flush=True)


def handler(job):
    """Process a lip-sync job."""
    job_input = job.get("input", {})
    image_b64 = job_input.get("image_base64")
    audio_b64 = job_input.get("audio_base64")

    if not image_b64 or not audio_b64:
        return {"error": "Both image_base64 and audio_base64 are required"}

    still_mode = job_input.get("still_mode", True)
    enhancer = job_input.get("enhancer", "gfpgan")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Decode inputs
        image_path = tmpdir / "input.png"
        audio_path = tmpdir / "input.wav"
        result_dir = tmpdir / "result"
        result_dir.mkdir()

        image_path.write_bytes(base64.b64decode(image_b64))
        audio_path.write_bytes(base64.b64decode(audio_b64))

        print(f"[JOB] image={image_path.stat().st_size / 1e3:.1f}KB, audio={audio_path.stat().st_size / 1e3:.1f}KB", flush=True)

        # Run SadTalker
        cmd = [
            sys.executable,
            str(SADTALKER_DIR / "inference.py"),
            "--driven_audio", str(audio_path),
            "--source_image", str(image_path),
            "--result_dir", str(result_dir),
            "--preprocess", "crop",
        ]
        if still_mode:
            cmd.append("--still")
        if enhancer:
            cmd.extend(["--enhancer", enhancer])

        print(f"[JOB] Running SadTalker...", flush=True)
        start = time.time()

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(SADTALKER_DIR),
        )

        elapsed = time.time() - start
        print(f"[JOB] SadTalker finished in {elapsed:.1f}s, exit={result.returncode}", flush=True)

        if result.returncode != 0:
            stderr_tail = result.stderr[-1000:] if result.stderr else ""
            return {
                "error": f"SadTalker failed (exit {result.returncode})",
                "stderr": stderr_tail,
            }

        # Find output video
        videos = list(result_dir.rglob("*.mp4"))
        if not videos:
            return {"error": "No output video generated", "stdout": result.stdout[-500:]}

        video_path = videos[0]
        video_b64 = base64.b64encode(video_path.read_bytes()).decode()

        print(f"[JOB] Success! Video: {video_path.stat().st_size / 1e6:.1f}MB, time: {elapsed:.1f}s", flush=True)

        return {
            "status": "success",
            "video_base64": video_b64,
            "processing_time": round(elapsed, 1),
        }


if __name__ == "__main__":
    print("[INFO] Downloading/verifying models...", flush=True)
    ensure_models()
    print("[INFO] Models ready. Starting RunPod handler...", flush=True)
    runpod.serverless.start({"handler": handler})
