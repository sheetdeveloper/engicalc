"""Getting a chart out of the window and into a document.

A chart you can only look at is half a result. These are the two things
anybody actually wants to do with one - save it to attach, or paste it into
what they are writing - and they are written once here because six tabs need
them and the seventh will.

PDF and SVG sit beside PNG in the save dialog on purpose. A bending moment
diagram that has to go on a drawing at A3 should not be a photograph of one.
"""

from __future__ import annotations

import io
import os
import tempfile
from tkinter import filedialog

from . import clipboard

#: What a chart can be saved as.
FORMATS = [("PNG image", "*.png"), ("PDF", "*.pdf"), ("SVG drawing", "*.svg")]

#: Dots per inch for a saved or copied PNG. Enough for a page at full width
#: without making a file nobody can email.
DPI = 200


def _write(figure, target, **kwargs) -> None:
    """Save *figure*, keeping the white ground it is drawn on.

    Without the face colour the background saves transparent, and a
    transparent PNG pasted into Word turns black in some versions of it.
    """
    figure.savefig(target, bbox_inches="tight",
                   facecolor=figure.get_facecolor(), **kwargs)


def save_figure(figure, name: str = "chart") -> str | None:
    """Ask where to put *figure* and write it there.

    Returns the path, or None if the dialog was cancelled.
    """
    path = filedialog.asksaveasfilename(
        defaultextension=".png", filetypes=FORMATS,
        initialfile=f"{name}.png")
    if not path:
        return None
    # Vector formats have no dots per inch to speak of, and matplotlib is
    # happy to be told anyway - it only affects the raster ones.
    _write(figure, path, dpi=DPI)
    return path


def figure_image(figure):
    """*figure* as a PIL image, at the resolution a save would give."""
    from PIL import Image

    buffer = io.BytesIO()
    _write(figure, buffer, format="png", dpi=DPI)
    buffer.seek(0)
    image = Image.open(buffer)
    image.load()              # before the buffer goes out of scope
    return image


def copy_figure(figure) -> None:
    """Put *figure* on the clipboard, ready to paste into a document."""
    clipboard.copy_image(figure_image(figure))


class temporary_png:
    """*figure* written to a PNG that exists for as long as it is needed.

    A workbook holds the picture by filename until it is saved, so the file
    has to outlive the call that made it and be gone afterwards.
    """

    def __init__(self, figure, dpi: int = 150):
        self.figure, self.dpi, self.path = figure, dpi, None

    def __enter__(self) -> str:
        handle, self.path = tempfile.mkstemp(suffix=".png")
        os.close(handle)
        _write(self.figure, self.path, dpi=self.dpi)
        return self.path

    def __exit__(self, *_exception) -> None:
        try:
            if self.path:
                os.unlink(self.path)
        except OSError:
            pass          # a temporary file nobody can delete is not an error
