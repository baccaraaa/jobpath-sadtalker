"""
Test the deployed RunPod Serverless SadTalker endpoint.
Usage: python test_endpoint.py <ENDPOINT_ID> <API_KEY>
"""
import base64
import json
import sys
import time
import requests

sys.stdout.reconfigure(encoding="utf-8")


def main():
    if len(sys.argv) < 3:
        print("Usage: python test_endpoint.py <ENDPOINT_ID> <API_KEY>")
        print("  or set RUNPOD_ENDPOINT_ID and RUNPOD_API_KEY env vars")
        endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "")
        api_key = os.environ.get("RUNPOD_API_KEY", "")
        if not endpoint_id or not api_key:
            sys.exit(1)
    else:
        endpoint_id = sys.argv[1]
        api_key = sys.argv[2]

    RUN_URL = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    STATUS_URL = f"https://api.runpod.ai/v2/{endpoint_id}/status"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Read test files
    print("Reading test files...")
    with open("Sofia.png", "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()
    with open("question.mp3", "rb") as f:
        # For now use MP3 — handler needs WAV, so convert first
        audio_raw = f.read()

    # Convert MP3 to PCM WAV using imageio-ffmpeg (if available)
    try:
        import imageio_ffmpeg
        import subprocess
        import tempfile

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        wav_path = tempfile.mktemp(suffix=".wav")
        subprocess.run(
            [ffmpeg, "-i", "question.mp3", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", wav_path, "-y"],
            capture_output=True, check=True,
        )
        with open(wav_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode()
        os.unlink(wav_path)
        print(f"Converted MP3 -> WAV ({len(audio_b64)} chars b64)")
    except ImportError:
        print("WARNING: imageio-ffmpeg not installed, sending raw MP3")
        audio_b64 = base64.b64encode(audio_raw).decode()

    print(f"Image: {len(image_b64)} chars, Audio: {len(audio_b64)} chars")

    # Submit job
    payload = {
        "input": {
            "image_base64": image_b64,
            "audio_base64": audio_b64,
            "still_mode": True,
            "enhancer": "gfpgan",
        }
    }

    print("\nSubmitting job...")
    resp = requests.post(RUN_URL, headers=headers, json=payload)
    result = resp.json()
    job_id = result.get("id")
    print(f"Job ID: {job_id}, Status: {result.get('status')}")

    if not job_id:
        print(f"Error: {json.dumps(result, indent=2)}")
        return

    # Poll
    start = time.time()
    while True:
        time.sleep(5)
        elapsed = int(time.time() - start)
        r = requests.get(f"{STATUS_URL}/{job_id}", headers=headers)
        data = r.json()
        status = data.get("status")
        exec_ms = data.get("executionTime", 0)
        delay_ms = data.get("delayTime", 0)
        print(f"  [{elapsed}s] {status} (exec={exec_ms / 1000:.0f}s, queue={delay_ms / 1000:.0f}s)")

        if status == "COMPLETED":
            output = data.get("output", {})
            if output.get("status") == "success" and output.get("video_base64"):
                video = base64.b64decode(output["video_base64"])
                with open("result.mp4", "wb") as f:
                    f.write(video)
                print(f"\n=== SUCCESS ===")
                print(f"Saved result.mp4 ({len(video):,} bytes)")
                print(f"Execution: {exec_ms / 1000:.1f}s")
            else:
                print(f"\nOutput: {json.dumps(output, indent=2, ensure_ascii=False)}")
            break

        elif status == "FAILED":
            error = data.get("error", "unknown")
            output = data.get("output", {})
            print(f"\nFAILED: {error}")
            if output.get("stderr"):
                print(f"Stderr (last 500): {output['stderr'][-500:]}")
            break

        elif elapsed > 600:
            print("\nTimeout 10m")
            break

    print("Done!")


import os

if __name__ == "__main__":
    main()
