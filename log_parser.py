import re
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


LOG_PATTERN = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'
    r' — (?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)'
    r' — (?P<logger>\S+)'
    r' — (?P<message>.+)'
)


def parse_log_file(log_path: Path, hours: int = 24) -> list[dict]:
    """
    Parse a log file and return entries from the past N hours only.

    Applies LOG_PATTERN to each line. Lines that do not match are
    skipped silently.

    # Silently skipping malformed lines is deliberate — real log files
    # always contain noise (truncated writes, encoding errors, injected
    # debug output). Crashing on bad lines would make the script
    # useless in production.

    The hours filter means the script always analyses a consistent
    time window regardless of how large the log file grows over time.

    Returns:
      [{"timestamp": datetime, "level": str, "logger": str,
        "message": str, "raw": str}, ...]
    """
    cutoff = datetime.now() - timedelta(hours=hours)
    entries = []

    with open(log_path, encoding='utf-8', errors='replace') as f:
        for raw_line in f:
            raw = raw_line.rstrip('\n')
            match = LOG_PATTERN.match(raw)
            if not match:
                continue
            ts = datetime.strptime(match.group('timestamp'), '%Y-%m-%dT%H:%M:%S')
            if ts < cutoff:
                continue
            entries.append({
                'timestamp': ts,
                'level':     match.group('level'),
                'logger':    match.group('logger'),
                'message':   match.group('message'),
                'raw':       raw,
            })

    return entries


def to_dataframe(entries: list[dict]) -> pd.DataFrame:
    """
    Convert parsed log entries to a pandas DataFrame.

    Adds three derived columns:
      hour          — hour of day (0-23), for hourly activity breakdown
      minute_window — timestamp floored to 5-minute intervals;
                      # this is the grouping key for spike detection —
                      # every entry in the same 5-minute bucket gets
                      # the same minute_window value so pandas can
                      # aggregate them together
      is_error      — True if level is ERROR or CRITICAL
    """
    if not entries:
        return pd.DataFrame(columns=[
            'timestamp', 'level', 'logger', 'message', 'raw',
            'hour', 'minute_window', 'is_error',
        ])

    df = pd.DataFrame(entries)
    df['hour'] = df['timestamp'].dt.hour
    df['minute_window'] = df['timestamp'].dt.floor('5min')
    df['is_error'] = df['level'].isin(['ERROR', 'CRITICAL'])
    return df
