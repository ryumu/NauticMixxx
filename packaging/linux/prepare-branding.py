#!/usr/bin/env python3
"""Embed the mandatory NauticMixxx PNG in Linux Qt resources before compiling."""
from pathlib import Path
from io import BytesIO
import sys
from PIL import Image


def write_if_changed(destination: Path, content: bytes) -> None:
    if not destination.exists() or destination.read_bytes() != content:
        destination.write_bytes(content)


def prepare(source: Path, project: Path) -> None:
    icon = project / 'branding/iCon-macOS-Dark-1024x1024@1x.png'
    with Image.open(icon) as image:
        if image.size != (1024, 1024):
            raise ValueError('The required project icon must be 1024x1024')
        image.load()
        destination = source / 'res/images/icons/nauticmixxx.png'
        write_if_changed(destination, icon.read_bytes())
        for size in (32, 64, 128, 256, 512):
            resized = BytesIO()
            image.resize((size, size), Image.Resampling.LANCZOS).save(resized, format='PNG')
            write_if_changed(source / f'res/images/icons/{size}x{size}/apps/mixxx.png',
                             resized.getvalue())
    defs = source / 'src/defs_urls.h'
    text = defs.read_text()
    old = ':/images/icons/scalable/apps/mixxx.svg'
    new = ':/images/icons/nauticmixxx.png'
    if old not in text and new not in text:
        raise ValueError('Unsupported upstream application icon definition')
    write_if_changed(defs, text.replace(old, new).encode())
    qrc = source / 'res/mixxx.qrc'
    text = qrc.read_text()
    old = '<file>images/icons/scalable/apps/mixxx.svg</file>'
    new = '<file>images/icons/nauticmixxx.png</file>'
    if old not in text and new not in text:
        raise ValueError('Unsupported upstream Qt resource collection')
    write_if_changed(qrc, text.replace(old, new).encode())


if __name__ == '__main__':
    prepare(Path(sys.argv[1]), Path(sys.argv[2]))
