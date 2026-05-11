"""
Responsible for loading random number data records from CSV files and
validating them.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd

from src.utils.types import RollRecord

_logger = logging.getLogger(__name__)

_REQUIRED_COLUMNS = [
    "server_seed",
    "client_seed",
    "nonce",
    "raw_output",
    "outcome",
    "timestamp",
    "mechanism_id",
]


def load_rng_data_records_from(file: str | Path) -> List[RollRecord]:
    """
    Loads all the random values (rolls, numbers, etc.) from the
    provided CSV file, validates the required fields, and returns a list of
    ValueRecord objects.
    """

    path = Path(file)

    if not path.exists():
        raise FileNotFoundError(f"Value record file {path} does not exist")

    df = pd.read_csv(path)

    missing_columns = set(_REQUIRED_COLUMNS) - set(df.columns)
    if missing_columns:
        raise ValueError(f"The CSV is missing required columns: {sorted(missing_columns)}")

    original_len = len(df)
    df = df.dropna(subset=_REQUIRED_COLUMNS)
    df = df[df[_REQUIRED_COLUMNS].apply(lambda col: col.str.strip() != "").all(axis=1)]
    dropped = original_len - len(df)

    if dropped > 0:
        _logger.warning(f"{dropped} row(s) dropped from {path} due to missing or invalid fields.")

    records = []
    parse_failures = 0
    line_number = 1  # accounts for header row

    for _, row in df.iterrows():
        line_number += 1
        try:
            record = _parse_row(row, line_number)
            records.append(record)
        except (ValueError, TypeError) as e:
            _logger.debug(f"Line {line_number} dropped during parsing: {e}")
            parse_failures += 1

    total_dropped = dropped + parse_failures
    if total_dropped > 0:
        _logger.warning(
            f"{total_dropped} row(s) dropped from {path} "
            f"({dropped} null/empty, {parse_failures} parse failures)."
        )

    _logger.info(f"Loaded {len(records)} valid roll records from {path}.")
    return records


def _parse_row(row: pd.DataFrame, line_number: int) -> RollRecord | None:
    """
    Parse and validate a single CSV row into a RollRecord.
    Returns None if any field is missing, null, or unparseable.
    """
    try:
        outcome = int(row["outcome"])
    except ValueError:
        _logger.warning(
            f"Line {line_number} dropped because the 'outcome' is not a " +
            "valid integer ({row['outcome']})."
        )
        return None

    try:
        raw_output = bytes.fromhex(row["raw_output"].strip())
    except ValueError:
        _logger.debug(
            f"Line {line_number} dropped because the 'raw_output' is not " +
            "valid hex ({row['raw_output']})."
        )
        return None

    try:
        timestamp = _parse_timestamp(row["timestamp"].strip())
    except ValueError:
        _logger.debug(
            f"Line {line_number} dropped because the 'timestamp' could not " +
            "be parsed ({row['timestamp']})."
        )
        return None

    return RollRecord(
        server_seed=row["server_seed"].strip(),
        client_seed=row["client_seed"].strip(),
        nonce=row["nonce"].strip(),
        raw_output=raw_output,
        outcome=outcome,
        timestamp=timestamp,
        mechanism_id=row["mechanism_id"].strip(),
    )


def _parse_timestamp(value: str) -> datetime | None:
    """
    Parse a timestamp string into a timezone-aware UTC datetime. With the
    capability to handle ISO 8601 strings. If the parsed datetime has no
    timezone, None is returned.
    """
    dt = datetime.fromisoformat(value)
    if dt.tzinfo:
        return dt
    return None
