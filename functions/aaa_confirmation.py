"""Підтвердження дій для GUI (legacy обгортка)."""

import logging

logger = logging.getLogger("aaa_confirmation")

_gui_instance = None

def set_gui_instance(gui):
    """Встановити глобальний екземпляр GUI для діалогів підтвердження."""
    global _gui_instance
    _gui_instance = gui
    logger.info("GUI instance set for confirmation dialogs")

def get_gui_instance():
    """Отримати глобальний екземпляр GUI."""
    return _gui_instance