import re
from datetime import datetime
from pathlib import Path

HADOOP_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ '
    r'(INFO|WARN|ERROR|FATAL) '
    r'\[([^\]]+)\] '
    r'(\S+): '
    r'(.+)$'
)

LEVEL_MAP = {
    'INFO':  'INFO',
    'WARN':  'WARNING',
    'ERROR': 'ERROR',
    'FATAL': 'CRITICAL',
}


def load_hadoop_logs(data_dir: Path) -> list[dict]:
    """
    Read all *.log files under data_dir, parse Hadoop log format, and return
    entries sorted by timestamp.

    Format: 2015-10-17 21:24:07,348 LEVEL [thread] component: message

    Stack trace continuation lines (no timestamp) are skipped — the
    triggering log line is already captured with the correct level.

    Returns entries in the same shape as log_parser.parse_log_file so the
    rest of the pipeline (to_dataframe, analyser, visualise) is unchanged.
    """
    entries = []
    for log_file in sorted(data_dir.rglob('*.log')):
        with open(log_file, encoding='utf-8', errors='replace') as f:
            for raw_line in f:
                raw = raw_line.rstrip('\n')
                m = HADOOP_PATTERN.match(raw)
                if not m:
                    continue
                ts = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
                entries.append({
                    'timestamp': ts,
                    'level':     LEVEL_MAP[m.group(2)],
                    'logger':    m.group(4).split('.')[-1],
                    'message':   m.group(5),
                    'raw':       raw,
                })

    entries.sort(key=lambda e: e['timestamp'])
    return entries
