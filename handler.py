"""
RunPod Serverless Handler — SadTalker Lip-Sync
Input:  base64 image + base64 WAV audio
Output: base64 MP4 video
"""
import base64
import glob
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import runpod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sadtalker-handler")

SADTALKER_DIR = "/app/SadTalker"
CHECKPOINT_DIR = f"{SADTALKER_DIR}/checkpoints"
TMP_DIR = "/tmp/sadtalker"
os.makedirs(TMP_DIR, exist_ok=True)


def handler(job):
    """
    SadTalker lip-sync handler.

    Input:
        image_base64: base64-encoded PNG/JPG image
        audio_base64: base64-encoded WAV audio (PCM 16-bit)
        still_mode:   use still mode — less head movement (default: true)
        enhancer:     face enhancer — "gfpgan" or none (default: "gfpgan")

    Output:
        status:       "success" or "error"
        video_base64: base64-encoded MP4 video (on success)
        error:        error message (on failure)
    """
    try:
        job_input = job["input"]

        image_b64 = job_input.get("image_base64")
        audio_b64 = job_input.get("audio_base64")
        still_mode = job_input.get("still_mode", True)
        enhancer = job_input.get("enhancer", "gfpgan")

        if not image_b64:
            return {"status": "error", "error": "image_base64 is required"}
        if not audio_b64:
            return {"status": "error", "error": "audio_base64 is required"}

        # Create unique working directory
        job_id = str(uuid4())[:8]
        work_dir = Path(TMP_DIR) / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        result_dir = work_dir / "results"
        result_dir.mkdir(exist_ok=True)

        # Decode input files
        image_path = work_dir / "input.png"
        audio_path = work_dir / "input.wav"

        image_path.write_bytes(base64.b64decode(image_b64))
        audio_path.write_bytes(base64.b64decode(audio_b64))

        logger.info(
            f"Job {job_id}: image={image_path.stat().st_size}B, "
            f"audio={audio_path.stat().st_size}B"
        )

        # Build SadTalker command
        cmd = [
            sys.executable,
            f"{SADTALKER_DIR}/inference.py",
            "--driven_audio", str(audio_path),
            "--source_image", str(image_path),
            "--result_dir", str(result_dir),
            "--checkpoint_dir", CHECKPOINT_DIR,
            "--preprocess", "crop",
        ]

        if still_mode:
            cmd.append("--still")

        if enhancer and enhancer != "none":
            cmd.extend(["--enhancer", enhancer])

        logger.info(f"Job {job_id}: running SadTalker...")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=SADTALKER_DIR,
        )

        if proc.returncode != 0:
            logger.error(f"Job {job_id}: SadTalker failed:\n{proc.stderr[-2000:]}")
            return {
                "status": "error",
                "error": f"SadTalker failed (exit {proc.returncode})",
                "stderr": proc.stderr[-2000:],
            }

        # Find output video
        mp4_files = glob.glob(str(result_dir / "**" / "*.mp4"), recursive=True)
        if not mp4_files:
            return {"status": "error", "error": "No output video generated"}

        video_path = mp4_files[0]
        video_bytes = Path(video_path).read_bytes()
        video_b64 = base64.b64encode(video_bytes).decode()

        logger.info(
            f"Job {job_id}: done, video={len(video_bytes)} bytes"
        )

        # Cleanup
        _cleanup(work_dir)

        return {
            "status": "success",
            "video_base64": video_b64,
        }

    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "SadTalker timed out (300s)"}
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


def _cleanup(work_dir: Path):
    """Remove temp files"""
    import shutil
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:
        pass


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
