"""Put a picture on the clipboard, so a calculation can be pasted into Word.

Tk's own clipboard handles text and nothing else. Word, PowerPoint, Outlook
and OneNote all paste a bitmap happily, so the useful thing to hand them is
``CF_DIB`` - a device-independent bitmap, which is a BMP file without its
14-byte file header.

The LaTeX goes on at the same time as ``CF_UNICODETEXT``. One clipboard can
hold several formats at once, and each application takes the one it
understands: Word takes the picture, a text editor takes the LaTeX. That way
one button does the right thing everywhere rather than making the user choose
in advance.
"""

from __future__ import annotations

import ctypes
import io
import sys
from ctypes import wintypes

CF_DIB = 8
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class ClipboardError(RuntimeError):
    """Raised when the clipboard could not be written to."""


def available() -> bool:
    return sys.platform == "win32"


def _win32():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
    return user32, kernel32


def _as_global(kernel32, payload: bytes):
    """Copy *payload* into a moveable global block the clipboard can own."""
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(payload))
    if not handle:
        raise ClipboardError("Could not allocate memory for the clipboard.")
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        raise ClipboardError("Could not lock memory for the clipboard.")
    ctypes.memmove(pointer, payload, len(payload))
    kernel32.GlobalUnlock(handle)
    return handle


def _to_dib(image) -> bytes:
    """A PIL image as a DIB: a BMP with the file header removed.

    Flattened onto white first - a document wants a white background, and a
    transparent PNG pasted into Word turns black in some versions.
    """
    from PIL import Image

    if image.mode in ("RGBA", "LA", "P"):
        flat = Image.new("RGB", image.size, "white")
        rgba = image.convert("RGBA")
        flat.paste(rgba, mask=rgba.split()[-1])
        image = flat
    else:
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, "BMP")
    return buffer.getvalue()[14:]


def copy_image(image, text: str | None = None) -> None:
    """Put *image* (a PIL image) on the clipboard, with *text* alongside."""
    if not available():
        raise ClipboardError(
            "Copying a picture to the clipboard is only supported on Windows. "
            "Use Save as image instead.")

    user32, kernel32 = _win32()
    payload = _to_dib(image)

    if not user32.OpenClipboard(None):
        raise ClipboardError("Another program is holding the clipboard open.")
    try:
        user32.EmptyClipboard()
        handle = _as_global(kernel32, payload)
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            raise ClipboardError("The clipboard refused the picture.")
        # The clipboard owns `handle` now - freeing it here would be a
        # double free the moment anything pasted.
        if text:
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            text_handle = _as_global(kernel32, encoded)
            if not user32.SetClipboardData(CF_UNICODETEXT, text_handle):
                kernel32.GlobalFree(text_handle)
    finally:
        user32.CloseClipboard()
