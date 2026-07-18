from __future__ import annotations

import subprocess
import sys
from pathlib import Path


TASK_NAME = "AutoFire Daily Reminder"


def command_for_reminder() -> str:
    """Build a Windows Task Scheduler command for either source or packaged mode."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}" --reminder'
    app = Path(__file__).resolve().parents[1] / "app.py"
    return f'"{Path(sys.executable)}" "{app}" --reminder'


def configure_daily_reminder(time_value: str) -> tuple[bool, str]:
    """Create or replace an interactive task for the currently signed-in Windows user."""
    try:
        subprocess.run(
            [
                "schtasks",
                "/Create",
                "/TN",
                TASK_NAME,
                "/TR",
                command_for_reminder(),
                "/SC",
                "DAILY",
                "/ST",
                time_value,
                "/F",
                "/IT",
            ],
            check=True,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        return False, detail.strip()
    return True, "已创建每日提醒任务"


def remove_daily_reminder() -> tuple[bool, str]:
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            check=True,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        return False, detail.strip()
    return True, "已移除每日提醒任务"
