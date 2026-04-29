"""ComfyUI integration for image generation (Phase 10).

Provides functions for:
- Connecting to ComfyUI API
- Generating images from text prompts
- Running custom workflows
- Managing image generation parameters
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False


class ComfyUIClient:
    """Клієнт для ComfyUI API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        """
        Args:
            base_url: URL ComfyUI сервера
        """
        self.base_url = base_url
        self.client_id = "agent_comfyui_client"

    def check_connection(self) -> Dict[str, Any]:
        """Перевірити з'єднання з ComfyUI.

        Returns:
            dict з success, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            response = requests.get(f"{self.base_url}/system_stats", timeout=5)
            if response.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка з'єднання: {str(e)}"}

    def get_queue_info(self) -> Dict[str, Any]:
        """Отримати інформацію про чергу.

        Returns:
            dict з success, queue_info, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            response = requests.get(f"{self.base_url}/queue", timeout=5)
            if response.status_code == 200:
                return {"success": True, "queue_info": response.json()}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка отримання черги: {str(e)}"}

    def get_history(self, prompt_id: Optional[str] = None) -> Dict[str, Any]:
        """Отримати історію виконання.

        Args:
            prompt_id: ID промпту (опційно)

        Returns:
            dict з success, history, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            url = f"{self.base_url}/history"
            if prompt_id:
                url = f"{url}/{prompt_id}"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                return {"success": True, "history": response.json()}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка отримання історії: {str(e)}"}

    def upload_image(self, image_path: str, overwrite: bool = True) -> Dict[str, Any]:
        """Завантажити зображення в ComfyUI.

        Args:
            image_path: Шлях до зображення
            overwrite: Перезаписати, якщо існує

        Returns:
            dict з success, filename, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        if not Path(image_path).exists():
            return {"success": False, "error": f"Файл не знайдено: {image_path}"}

        try:
            filename = Path(image_path).name
            with open(image_path, "rb") as f:
                files = {"image": (filename, f, "image/png")}
                data = {"overwrite": "true" if overwrite else "false"}
                
                response = requests.post(
                    f"{self.base_url}/upload/image",
                    files=files,
                    data=data,
                    timeout=30
                )
            
            if response.status_code == 200:
                return {"success": True, "filename": filename}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка завантаження: {str(e)}"}

    def get_view_metadata(self, filename: str, subfolder: str = "", type: str = "input") -> Dict[str, Any]:
        """Отримати метадані зображення.

        Args:
            filename: Ім'я файлу
            subfolder: Підпапка
            type: Тип (input/output)

        Returns:
            dict з success, metadata, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": type
            }
            
            response = requests.get(
                f"{self.base_url}/view_metadata",
                params=params,
                timeout=5
            )
            
            if response.status_code == 200:
                return {"success": True, "metadata": response.json()}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка отримання метаданих: {str(e)}"}

    def execute_workflow(self, workflow: Dict[str, Any], output_dir: str = "output") -> Dict[str, Any]:
        """Виконати workflow.

        Args:
            workflow: JSON workflow
            output_dir: Директорія для виводу

        Returns:
            dict з success, prompt_id, images, error
        """
        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            # Відправляємо промпт
            payload = {
                "prompt": workflow,
                "client_id": self.client_id
            }
            
            response = requests.post(
                f"{self.base_url}/prompt",
                json=payload,
                timeout=5
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
            
            result = response.json()
            prompt_id = result.get("prompt_id")
            
            if not prompt_id:
                return {"success": False, "error": "Не отримано prompt_id"}
            
            # Чекаємо завершення
            max_wait = 300  # 5 хвилин
            wait_interval = 1
            elapsed = 0
            
            while elapsed < max_wait:
                history = self.get_history(prompt_id)
                if history.get("success") and prompt_id in history.get("history", {}):
                    # Витягуємо зображення з історії
                    history_data = history["history"][prompt_id]
                    outputs = history_data.get("outputs", {})
                    
                    images = []
                    for node_id, node_output in outputs.items():
                        if "images" in node_output:
                            for img in node_output["images"]:
                                images.append({
                                    "filename": img["filename"],
                                    "subfolder": img.get("subfolder", ""),
                                    "type": img.get("type", "output")
                                })
                    
                    return {
                        "success": True,
                        "prompt_id": prompt_id,
                        "images": images,
                        "output_dir": output_dir
                    }
                
                time.sleep(wait_interval)
                elapsed += wait_interval
            
            return {"success": False, "error": "Таймаут очікування"}
        except Exception as e:
            return {"success": False, "error": f"Помилка виконання workflow: {str(e)}"}

    def generate_text_to_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        cfg: float = 7.0,
        seed: int = -1,
        output_dir: str = "output"
    ) -> Dict[str, Any]:
        """Генерувати зображення з тексту (Text-to-Image).

        Args:
            prompt: Текстовий промпт
            negative_prompt: Негативний промпт
            width: Ширина зображення
            height: Висота зображення
            steps: Кількість кроків
            cfg: CFG scale
            seed: Seed (-1 = random)
            output_dir: Директорія для виводу

        Returns:
            dict з success, images, prompt_id, error
        """
        # Базовий workflow для text-to-image
        workflow = {
            "3": {
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "4": {
                "inputs": {
                    "ckpt_name": "model.safetensors"
                },
                "class_type": "CheckpointLoaderSimple"
            },
            "5": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {
                    "text": prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        
        return self.execute_workflow(workflow, output_dir)

    def interrupt(self) -> Dict[str, Any]:
        "Перервати поточне виконання."

        if not REQUESTS_AVAILABLE:
            return {"success": False, "error": "requests не доступний"}

        try:
            response = requests.post(f"{self.base_url}/interrupt", timeout=5)
            if response.status_code == 200:
                return {"success": True}
            else:
                return {"success": False, "error": f"Статус код: {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": f"Помилка переривання: {str(e)}"}


def create_comfyui_client(base_url: str = "http://127.0.0.1:8188") -> ComfyUIClient:
    """Створити клієнт ComfyUI.

    Args:
        base_url: URL ComfyUI сервера

    Returns:
        ComfyUIClient
    """
    return ComfyUIClient(base_url)
