"""
Minimal debug handler — just echoes back to verify RunPod infrastructure works.
"""
import runpod
import os
import sys

print(f"[DEBUG] Python: {sys.version}", flush=True)
print(f"[DEBUG] runpod version: {runpod.__version__}", flush=True)
print(f"[DEBUG] CWD: {os.getcwd()}", flush=True)
print(f"[DEBUG] Handler starting...", flush=True)


def handler(job):
    """Simple echo handler for debugging."""
    print(f"[DEBUG] Got job: {job.get('id', 'unknown')}", flush=True)
    job_input = job.get("input", {})

    # Check what files exist
    sadtalker_exists = os.path.isdir("/SadTalker")
    checkpoints_exist = os.path.isdir("/SadTalker/checkpoints")

    checkpoint_files = []
    if checkpoints_exist:
        for f in os.listdir("/SadTalker/checkpoints"):
            checkpoint_files.append(f)

    return {
        "status": "debug_ok",
        "message": "Handler received the job successfully",
        "sadtalker_dir_exists": sadtalker_exists,
        "checkpoints_exist": checkpoints_exist,
        "checkpoint_files": checkpoint_files[:20],
        "input_keys": list(job_input.keys()),
        "python_version": sys.version,
        "runpod_version": runpod.__version__,
    }


if __name__ == "__main__":
    print("[DEBUG] Calling runpod.serverless.start()...", flush=True)
    runpod.serverless.start({"handler": handler})
