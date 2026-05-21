"""
Тести для модуля core_gui_guardian.py

GUI Automation Phase 6 — GUI Guardian (захист від небезпечних дій).
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Додаємо батьківську папку в шлях
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestGUIGuardian:
    """Тести для класу GUIGuardian."""

    def test_init(self):
        """Тест ініціалізації GUIGuardian."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        assert guardian is not None
        assert guardian.sandbox_mode == False

    def test_is_action_allowed_safe(self):
        """Тест дозволеної безпечної дії."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        result = guardian.is_action_allowed("mouse_click", {"x": 100, "y": 200})
        assert result["allowed"] == True
        assert "risk" in result

    def test_is_action_allowed_dangerous_text(self):
        """Тест блокування небезпечної дії з критичним текстом."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        # Багато небезпечних патернів дадуть CRITICAL
        result = guardian.is_action_allowed("delete_file", {"path": "important.txt"}, target_text="delete remove format wipe")
        assert result["allowed"] == False
        assert result["risk"].level.value in ("critical", "high")

    def test_assess_risk_low(self):
        """Тест низького ризику."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        assessment = guardian.assess_risk("mouse_click", {"x": 100, "y": 200})
        assert assessment.level.value == "low"
        assert assessment.score < 0.2

    def test_assess_risk_dangerous(self):
        """Тест підвищеного ризику при небезпечному тексті."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        assessment = guardian.assess_risk("click", {"x": 100, "y": 200}, target_text="delete all files")
        assert assessment.score >= 0.3
        assert len(assessment.reasons) > 0

    def test_sandbox_mode_enable_disable(self):
        """Тест увімкнення/вимкнення sandbox режиму."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.enable_sandbox_mode()
        assert guardian.sandbox_mode == True

        guardian.disable_sandbox_mode()
        assert guardian.sandbox_mode == False

    def test_sandbox_blocks_outside_region(self):
        """Тест блокування дій за межами дозволеної зони."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.enable_sandbox_mode(allowed_region=(0, 0, 100, 100))

        # Дія всередині зони
        result = guardian.is_action_allowed("mouse_click", {"x": 50, "y": 50})
        assert result["allowed"] == True

        # Дія за межами зони
        result = guardian.is_action_allowed("mouse_click", {"x": 500, "y": 500})
        assert result["allowed"] == False

    def test_set_allowed_applications(self):
        """Тест встановлення дозволених програм."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.set_allowed_applications(["notepad", "explorer"])

        assert "notepad" in guardian.allowed_applications
        assert "explorer" in guardian.allowed_applications

    def test_add_blocked_application(self):
        """Тест додавання програми в чорний список."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.add_blocked_application("cmd.exe")

        assert "cmd.exe" in guardian.blocked_applications

    def test_preview_action(self):
        """Тест створення preview дії."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        preview = guardian.preview_action("mouse_click", {"x": 100, "y": 200})

        assert "Клік миші" in preview or "100" in preview

    def test_simulate_action(self):
        """Тест симуляції дії."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        result = guardian.simulate_action("mouse_click", {"x": 100, "y": 200})

        assert "would_succeed" in result
        assert "preview" in result
        assert "risk" in result

    def test_get_safety_report(self):
        """Тест генерації звіту безпеки."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        report = guardian.get_safety_report()

        assert "Guardian Safety Report" in report
        assert "Sandbox mode" in report

    def test_set_allowed_region(self):
        """Тест встановлення дозволеної зони."""
        from functions.gui.core_gui_guardian import GUIGuardian

        guardian = GUIGuardian()
        guardian.set_allowed_region(0, 0, 1920, 1080)

        assert guardian.allowed_region is not None
        assert guardian.allowed_region.width == 1920
        assert guardian.allowed_region.height == 1080

    def test_api_functions(self):
        """Тест публічних API функцій."""
        from functions.gui.core_gui_guardian import (
            get_guardian, is_action_allowed, assess_risk,
            enable_sandbox_mode, disable_sandbox_mode,
            preview_action, get_safety_report
        )

        guardian = get_guardian()
        assert guardian is not None

        # Тест is_action_allowed
        result = is_action_allowed("mouse_click", {"x": 100, "y": 200})
        assert "allowed" in result

        # Тест assess_risk
        risk = assess_risk("mouse_click", {"x": 100, "y": 200})
        assert "level" in risk
        assert "score" in risk

        # Тест preview_action
        preview = preview_action("mouse_click", {"x": 100, "y": 200})
        assert isinstance(preview, str)

        # Тест get_safety_report
        report = get_safety_report()
        assert isinstance(report, str)


class TestRiskAssessment:
    """Тести для класу RiskAssessment."""

    def test_create_risk_assessment(self):
        """Тест створення оцінки ризику."""
        from functions.gui.core_gui_guardian import RiskAssessment, GUIRiskLevel

        assessment = RiskAssessment(
            level=GUIRiskLevel.MEDIUM,
            score=0.5,
            reasons=["test reason"],
            suggestions=["test suggestion"]
        )

        assert assessment.level == GUIRiskLevel.MEDIUM
        assert assessment.score == 0.5
        assert "test reason" in assessment.reasons


class TestSafetyZone:
    """Тести для класу SafetyZone."""

    def test_create_safety_zone(self):
        """Тест створення безпечної зони."""
        from functions.gui.core_gui_guardian import SafetyZone

        zone = SafetyZone(x=0, y=0, width=100, height=100, allowed_apps=["notepad"])
        assert zone.x == 0
        assert zone.y == 0
        assert zone.width == 100
        assert zone.height == 100


class TestGuardedDecorator:
    """Тести для декоратора guarded."""

    def test_guarded_decorator_blocks_critical(self):
        """Тест блокування критичної дії декоратором."""
        from functions.gui.core_gui_guardian import guarded

        @guarded("delete_file")
        def dangerous_action():
            return {"success": True}

        result = dangerous_action()
        # Має бути заблоковано через високий ризик
        assert result.get("blocked", False) == True or result.get("success", False) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])