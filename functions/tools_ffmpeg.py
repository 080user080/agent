"""FFmpeg wrapper for video/audio processing (Phase 10).

Provides functions for:
- Converting video/audio formats
- Extracting audio from video
- Trimming/cutting videos
- Extracting frames from video
- Creating thumbnails
- Getting video/audio metadata
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


def check_ffmpeg_available() -> Dict[str, Any]:
    """Перевірити, чи встановлений ffmpeg.

    Returns:
        dict з success, version, error
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split("\n")[0]
            return {"success": True, "version": version_line}
        else:
            return {"success": False, "error": "ffmpeg не знайдено"}
    except Exception as e:
        return {"success": False, "error": f"Помилка перевірки: {str(e)}"}


def get_video_metadata(file_path: str) -> Dict[str, Any]:
    """Отримати метадані відео/аудіо файлу.

    Args:
        file_path: Шлях до файлу

    Returns:
        dict з success, metadata (duration, codec, resolution, etc.), error
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"Файл не знайдено: {file_path}"}

    try:
        # Використовує ffprobe для отримання метаданих
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return {"success": False, "error": f"ffprobe помилка: {result.stderr}"}

        metadata = json.loads(result.stdout)
        
        # Витягуємо основну інформацію
        format_info = metadata.get("format", {})
        streams = metadata.get("streams", [])
        
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        
        result_data = {
            "duration": float(format_info.get("duration", 0)),
            "size": int(format_info.get("size", 0)),
            "format_name": format_info.get("format_name", ""),
            "bit_rate": int(format_info.get("bit_rate", 0)),
        }
        
        if video_stream:
            result_data["video"] = {
                "codec": video_stream.get("codec_name", ""),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                "bit_rate": int(video_stream.get("bit_rate", 0)),
            }
        
        if audio_stream:
            result_data["audio"] = {
                "codec": audio_stream.get("codec_name", ""),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "channels": int(audio_stream.get("channels", 0)),
                "bit_rate": int(audio_stream.get("bit_rate", 0)),
            }
        
        return {"success": True, "metadata": result_data}
    except Exception as e:
        return {"success": False, "error": f"Помилка отримання метаданих: {str(e)}"}


def convert_video(input_path: str, output_path: str, codec: str = "libx264", 
                  crf: int = 23, preset: str = "medium") -> Dict[str, Any]:
    """Конвертувати відео в інший формат.

    Args:
        input_path: Вхідний файл
        output_path: Вихідний файл
        codec: Відео кодек (libx264, libx265, etc.)
        crf: Якість (0-51, менше = краща якість)
        preset: Пресет (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)

    Returns:
        dict з success, output_path, error
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Вхідний файл не знайдено: {input_path}"}

    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-c:v", codec,
            "-crf", str(crf),
            "-preset", preset,
            "-c:a", "aac",
            "-y",  # Перезаписати, якщо файл існує
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 година таймаут
        )
        
        if result.returncode == 0:
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка конвертації: {str(e)}"}


def extract_audio(input_path: str, output_path: str, codec: str = "aac") -> Dict[str, Any]:
    """Витягти аудіо з відео.

    Args:
        input_path: Вхідний відео файл
        output_path: Вихідний аудіо файл
        codec: Аудіо кодек (aac, mp3, libmp3lame)

    Returns:
        dict з success, output_path, error
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Вхідний файл не знайдено: {input_path}"}

    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vn",  # Без відео
            "-c:a", codec,
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка витягування аудіо: {str(e)}"}


def trim_video(input_path: str, output_path: str, start_time: str, 
                duration: Optional[str] = None, end_time: Optional[str] = None) -> Dict[str, Any]:
    """Обрізати відео.

    Args:
        input_path: Вхідний файл
        output_path: Вихідний файл
        start_time: Час початку (HH:MM:SS або секунди)
        duration: Тривалість (HH:MM:SS або секунди)
        end_time: Час кінця (HH:MM:SS або секунди) - альтернатива до duration

    Returns:
        dict з success, output_path, error
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Вхідний файл не знайдено: {input_path}"}

    try:
        cmd = ["ffmpeg", "-i", input_path, "-ss", start_time]
        
        if duration:
            cmd.extend(["-t", duration])
        elif end_time:
            cmd.extend(["-to", end_time])
        
        cmd.extend(["-c", "copy", "-y", output_path])  # copy для швидкості
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка обрізки: {str(e)}"}


def extract_frames(input_path: str, output_dir: str, fps: float = 1.0, 
                   start_time: Optional[str] = None, duration: Optional[str] = None) -> Dict[str, Any]:
    """Витягти кадри з відео.

    Args:
        input_path: Вхідний файл
        output_dir: Директорія для збереження кадрів
        fps: Кадрів на секунду
        start_time: Час початку (опційно)
        duration: Тривалість (опційно)

    Returns:
        dict з success, frame_count, output_dir, error
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Вхідний файл не знайдено: {input_path}"}

    os.makedirs(output_dir, exist_ok=True)
    
    try:
        cmd = ["ffmpeg", "-i", input_path]
        
        if start_time:
            cmd.extend(["-ss", start_time])
        if duration:
            cmd.extend(["-t", duration])
        
        cmd.extend([
            "-vf", f"fps={fps}",
            f"{output_dir}/frame_%04d.png",
            "-y"
        ])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        if result.returncode == 0:
            # Порахувати кількість кадрів
            frame_count = len([f for f in os.listdir(output_dir) if f.startswith("frame_")])
            return {"success": True, "frame_count": frame_count, "output_dir": output_dir}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка витягування кадрів: {str(e)}"}


def create_thumbnail(input_path: str, output_path: str, timestamp: str = "00:00:01", 
                    width: int = 320, height: int = -1) -> Dict[str, Any]:
    """Створити мініатюру для відео.

    Args:
        input_path: Вхідний файл
        output_path: Вихідний файл
        timestamp: Часовий штамп для кадру
        width: Ширина мініатюри
        height: Висота мініатюри (-1 = auto)

    Returns:
        dict з success, output_path, error
    """
    if not os.path.exists(input_path):
        return {"success": False, "error": f"Вхідний файл не знайдено: {input_path}"}

    try:
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-ss", timestamp,
            "-vframes", "1",
            "-vf", f"scale={width}:{height}",
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка створення мініатюри: {str(e)}"}


def combine_videos(input_paths: List[str], output_path: str, concat_file: Optional[str] = None) -> Dict[str, Any]:
    """Об'єднати кілька відео в одне.

    Args:
        input_paths: Список вхідних файлів
        output_path: Вихідний файл
        concat_file: Шлях до файлу зі списком (опційно)

    Returns:
        dict з success, output_path, error
    """
    if not input_paths:
        return {"success": False, "error": "Список вхідних файлів порожній"}
    
    for path in input_paths:
        if not os.path.exists(path):
            return {"success": False, "error": f"Файл не знайдено: {path}"}

    try:
        # Створюємо concat файл, якщо не передано
        if concat_file is None:
            concat_file = output_path + ".txt"
        
        with open(concat_file, "w") as f:
            for path in input_paths:
                abs_path = os.path.abspath(path)
                f.write(f"file '{abs_path}'\n")
        
        cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600
        )
        
        # Видаляємо тимчасовий файл
        if os.path.exists(concat_file):
            os.remove(concat_file)
        
        if result.returncode == 0:
            return {"success": True, "output_path": output_path}
        else:
            return {"success": False, "error": f"ffmpeg помилка: {result.stderr}"}
    except Exception as e:
        return {"success": False, "error": f"Помилка об'єднання: {str(e)}"}
