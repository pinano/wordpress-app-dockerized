"""
media_processor.py — ffmpeg helpers for the Telegram bot.

All paths here are local to the **bot container**.
The DOWNLOAD_PATH is a shared volume also mounted in the app container.
"""
import logging
import os
import subprocess
from pathlib import Path

import config

logger = logging.getLogger(__name__)


def _ffmpeg(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    cmd = [config.FFMPEG_PATH, "-y", *args]
    logger.debug("ffmpeg: %s", " ".join(cmd))
    
    # Run ffmpeg, piping stderr (ffmpeg uses stderr for normal output/progress)
    process = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True)
    
    output_lines = []
    if process.stderr:
        for line in iter(process.stderr.readline, ""):
            line_stripped = line.strip()
            if line_stripped:
                logger.info("[ffmpeg] %s", line_stripped)
                output_lines.append(line_stripped)
                
    process.wait(timeout=timeout)
    
    if process.returncode != 0:
        logger.error("ffmpeg error (exit %d)", process.returncode)
        raise subprocess.CalledProcessError(process.returncode, cmd, output="\n".join(output_lines))
        
    return process


def extract_thumbnail(video_path: str, thumbnail_path: str, seek: float = 1.0) -> str:
    """
    Extract a single frame from video_path at `seek` seconds and save as JPEG.
    Returns thumbnail_path.
    """
    Path(thumbnail_path).parent.mkdir(parents=True, exist_ok=True)
    # Use -vf "scale=1280:-1" to ensure a decent size thumbnail, or just let it be the original size
    # By default ffmpeg extracts the original resolution frame. We'll add -q:v 2 for high JPEG quality.
    _ffmpeg("-ss", str(seek), "-i", video_path, "-vframes", "1", "-q:v", "2", thumbnail_path)
    return thumbnail_path


def convert_mov_to_mp4(input_path: str, output_path: str) -> str:
    """
    Stream-copy a MOV container to MP4 (no re-encode).
    Returns output_path.
    """
    _ffmpeg("-i", input_path, "-vcodec", "copy", "-acodec", "copy", output_path)
    return output_path


def convert_audio_to_mp3_vbr(input_path: str, output_path: str) -> str:
    """
    Convert any audio file to MP3 VBR (libmp3lame, stereo, quality 2).
    Returns output_path.
    """
    _ffmpeg("-i", input_path, "-c:a", "libmp3lame", "-ac", "2", "-q:a", "2", output_path)
    return output_path


def media_subdir(file_relative_path: str) -> str:
    """Return the top-level category inferred from a Telegram file path like 'videos/file_X.mp4'."""
    parts = Path(file_relative_path).parts
    return parts[0] if parts else "documents"


def thumbnail_path_for(file_name: str) -> str:
    """Return the canonical thumbnail path inside DOWNLOAD_PATH/thumbnails/."""
    return os.path.join(config.DOWNLOAD_PATH, "thumbnails", f"{file_name}.thumb.jpg")
