"""Turn a file into units of text to scan [F02-FR-04].

A unit with ``location=None`` is plain text and is reported by line number. Other units carry their own
location (``Sheet1!B3``, ``word/document.xml``, ``r12c3``). Delta tables need no reader of their own: they
are parquet data files plus a JSON log, and both reach a reader here.
"""

import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl.utils.exceptions import InvalidFileException

BINARY_SNIFF_BYTES = 8192
UNREADABLE = (
    OSError,
    ValueError,
    KeyError,
    zipfile.BadZipFile,
    ET.ParseError,
    InvalidFileException,
    pa.ArrowException,
)


class SkippedFile(Exception):
    """The file was not scanned: it is binary or could not be read."""


@dataclass(frozen=True)
class Unit:
    location: str | None
    text: str


def read_units(path: Path) -> Iterator[Unit]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".xlsx":
            yield from _xlsx(path)
        elif suffix in {".docx", ".pptx"}:
            yield from _office_xml(path)
        elif suffix == ".parquet":
            yield from _parquet(path)
        else:
            yield from _text(path)
    except SkippedFile:
        raise
    except (
        OSError,
        ValueError,
        KeyError,
        zipfile.BadZipFile,
        ET.ParseError,
        InvalidFileException,
        pa.ArrowException,
    ) as error:
        raise SkippedFile(f"unreadable ({type(error).__name__})") from error


def _text(path: Path) -> Iterator[Unit]:
    data = path.read_bytes()
    if b"\x00" in data[:BINARY_SNIFF_BYTES]:
        raise SkippedFile("binary")
    yield Unit(None, data.decode("utf-8", errors="replace"))


def _xlsx(path: Path) -> Iterator[Unit]:
    book = openpyxl.load_workbook(path, read_only=True, data_only=False)
    try:
        props = book.properties
        fields = [props.creator, props.lastModifiedBy, props.title, props.subject, props.description]
        yield Unit("properties", "\n".join(f for f in fields if f))
        for sheet in book.worksheets:
            yield Unit("sheet-name", sheet.title)
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value is not None:
                        yield Unit(f"{sheet.title}!{cell.coordinate}", str(cell.value))
    finally:
        book.close()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _office_xml(path: Path) -> Iterator[Unit]:
    """Read every XML part of a docx or pptx. Paragraph runs are joined so split terms are found."""
    with zipfile.ZipFile(path) as archive:
        for name in sorted(archive.namelist()):
            if not name.endswith(".xml"):
                continue
            root = ET.fromstring(archive.read(name))
            paragraphs = ["".join(p.itertext()) for p in root.iter() if _local(p.tag) == "p"]
            if not paragraphs:
                paragraphs = [t for t in root.itertext() if t.strip()]
            yield Unit(name, "\n".join(paragraphs))


def _is_texty(kind: pa.DataType) -> bool:
    if pa.types.is_dictionary(kind):
        return _is_texty(kind.value_type)
    return bool(pa.types.is_string(kind) or pa.types.is_large_string(kind) or pa.types.is_nested(kind))


def _parquet(path: Path) -> Iterator[Unit]:
    """Column names, then every value of every string-like column (no row cap)."""
    reader = pq.ParquetFile(path)
    for number, name in enumerate(reader.schema_arrow.names, start=1):
        yield Unit(f"column#{number}", name)
    rows_before = 0
    for batch in reader.iter_batches():
        for number, column in enumerate(batch.columns, start=1):
            if not _is_texty(column.type):
                continue
            for offset, value in enumerate(column.to_pylist()):
                if value is not None:
                    yield Unit(f"r{rows_before + offset + 1}c{number}", str(value))
        rows_before += batch.num_rows
