"""Тести для functions/tools_visual_diff.py (VisualDiff).

Використовуємо реальні маленькі PIL-зображення замість mock-ів: PIL + numpy +
cv2 вже є в runtime-залежностях, тому це дешево і зрозуміло.
"""
import os
import sys
from unittest.mock import MagicMock

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from functions.tools_visual_diff import VisualDiff  # noqa: E402


@pytest.fixture
def diff(tmp_path):
    """VisualDiff із тимчасовим baseline-каталогом і мок-захопленням."""
    capture = MagicMock()
    return VisualDiff(baseline_dir=str(tmp_path / "baselines"), screen_capture=capture)


@pytest.fixture
def white_image():
    return Image.new("RGB", (50, 50), color="white")


@pytest.fixture
def black_image():
    return Image.new("RGB", (50, 50), color="black")


class TestCompareImages:
    def test_identical_images(self, diff, white_image):
        result = diff.compare_images(white_image, white_image)
        assert result["success"] is True
        assert bool(result["identical"]) is True
        assert result["diff_percent"] == 0
        assert result["changed_pixels"] == 0

    def test_completely_different_images(self, diff, white_image, black_image):
        result = diff.compare_images(white_image, black_image)
        assert result["success"] is True
        assert bool(result["identical"]) is False
        assert result["diff_percent"] > 99

    def test_different_sizes_autoscale(self, diff):
        """Якщо розміри різні — друге зображення масштабують до першого."""
        a = Image.new("RGB", (100, 100), color="white")
        b = Image.new("RGB", (50, 50), color="white")
        result = diff.compare_images(a, b)
        assert result["success"] is True
        assert result["total_pixels"] == 100 * 100

    def test_threshold_affects_identical_flag(self, diff, white_image):
        """Невелика пляма + високий поріг → identical=True."""
        img = white_image.copy()
        # Змінюємо крихітну область (~1% пікселів).
        for x in range(5):
            for y in range(5):
                img.putpixel((x, y), (0, 0, 0))

        # threshold=0.001 (0.1%) → зміна помітна.
        tight = diff.compare_images(white_image, img, threshold=0.001)
        assert bool(tight["identical"]) is False

        # threshold=0.5 (50%) → зміна не значуща.
        loose = diff.compare_images(white_image, img, threshold=0.5)
        assert bool(loose["identical"]) is True


class TestHighlightChanges:
    def test_returns_pil_image(self, diff, white_image, black_image):
        result = diff.highlight_changes(white_image, black_image)
        assert isinstance(result, Image.Image)
        # Розмір збігається з "after".
        assert result.size == black_image.size


class TestBaselines:
    def test_capture_baseline_saves_file(self, diff, white_image, tmp_path):
        """capture_baseline викликає capture і записує файл."""
        diff.capture.take_screenshot.return_value = {"success": True, "image": white_image}
        result = diff.capture_baseline("home_screen")

        assert result["success"] is True
        assert result["name"] == "home_screen"
        assert os.path.exists(result["path"])
        assert "home_screen" in diff._baselines

    def test_capture_baseline_capture_error(self, diff):
        diff.capture.take_screenshot.return_value = {"success": False, "error": "boom"}
        result = diff.capture_baseline("x")
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_compare_with_baseline_not_found(self, diff, white_image):
        result = diff.compare_with_baseline("missing", current_image=white_image)
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_compare_with_baseline_roundtrip(self, diff, white_image, black_image):
        # Створюємо baseline із white.
        diff.capture.take_screenshot.return_value = {"success": True, "image": white_image}
        diff.capture_baseline("roundtrip")

        # Порівнюємо з black → має бути changed.
        result = diff.compare_with_baseline("roundtrip", current_image=black_image)
        assert result["success"] is True
        assert result["changed"] is True
        assert result["diff_percent"] > 50

    def test_list_baselines_empty(self, diff):
        assert diff.list_baselines() == []

    def test_list_baselines_returns_created(self, diff, white_image):
        diff.capture.take_screenshot.return_value = {"success": True, "image": white_image}
        diff.capture_baseline("scene_a")
        diff.capture_baseline("scene_b")
        names = {b["name"] for b in diff.list_baselines()}
        assert names == {"scene_a", "scene_b"}

    def test_delete_baseline(self, diff, white_image):
        diff.capture.take_screenshot.return_value = {"success": True, "image": white_image}
        diff.capture_baseline("tmp")
        result = diff.delete_baseline("tmp")
        assert result["success"] is True
        assert diff.list_baselines() == []

    def test_delete_missing_baseline(self, diff):
        result = diff.delete_baseline("nope")
        assert result["success"] is False
