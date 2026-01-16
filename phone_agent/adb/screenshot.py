"""Screenshot utilities for capturing Android device screen."""

import base64
import subprocess
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple

from PIL import Image


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


def get_screenshot(device_id: str | None = None, timeout: int = 60) -> Screenshot:
    """
    Capture a screenshot from the connected Android device.

    Args:
        device_id: Optional ADB device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
    """
    adb_prefix = _get_adb_prefix(device_id)

    try:
        # Use exec-out to avoid device disk I/O; retry once on failure/timeout.
        last_error: Exception | None = None
        for _ in range(2):
            try:
                result = subprocess.run(
                    adb_prefix + ["exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=timeout,
                )
            except Exception as e:
                last_error = e
                continue

            stdout_bytes = result.stdout or b""
            stderr_text = ""
            if result.stderr:
                stderr_text = result.stderr.decode("utf-8", errors="ignore")

            if not stdout_bytes:
                if "Status: -1" in stderr_text or "Failed" in stderr_text:
                    return _create_fallback_screenshot(is_sensitive=True)
                last_error = RuntimeError("empty screenshot output")
                continue

            if not stdout_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
                combined_text = stderr_text
                try:
                    combined_text += stdout_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    pass
                if "Status: -1" in combined_text or "Failed" in combined_text:
                    return _create_fallback_screenshot(is_sensitive=True)
                last_error = RuntimeError("screenshot output is not PNG")
                continue

            img = Image.open(BytesIO(stdout_bytes))
            width, height = img.size
            base64_data = base64.b64encode(stdout_bytes).decode("utf-8")

            return Screenshot(
                base64_data=base64_data,
                width=width,
                height=height,
                is_sensitive=False,
            )

        if last_error:
            print(f"Screenshot warn: exec-out failed after retry: {last_error}")
            raise last_error
        return _create_fallback_screenshot(is_sensitive=False)

    except Exception as e:
        print(f"Screenshot error: {e}")
        return _create_fallback_screenshot(is_sensitive=False)


def _get_adb_prefix(device_id: str | None) -> list:
    """Get ADB command prefix with optional device specifier."""
    if device_id:
        return ["adb", "-s", device_id]
    return ["adb"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
    )
