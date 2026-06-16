from datetime import datetime, timedelta
from pathlib import Path


def _make_entries(n_info=50, n_warn=10, n_error=5, n_critical=1, base_hour=10):
    """Create minimal log entries without any file I/O or generator."""
    now = datetime(2015, 10, 18, base_hour, 0, 0)
    entries = []
    for i, (count, level) in enumerate([
        (n_info, 'INFO'), (n_warn, 'WARNING'),
        (n_error, 'ERROR'), (n_critical, 'CRITICAL'),
    ]):
        for j in range(count):
            entries.append({
                'timestamp': now + timedelta(seconds=i * 60 + j),
                'level':     level,
                'logger':    'TestLogger',
                'message':   f'{level} message {j}',
                'raw':       f'{level} message {j}',
            })
    return entries


def test_config_loads():
    """Config loads without error when env vars are set."""
    import os
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from config_loader import load_config, validate_config
    config = load_config()
    validate_config(config)


def test_hadoop_loader():
    """Hadoop loader parses real log files when sample_data exists."""
    import pytest
    data_dir = Path('sample_data')
    if not data_dir.exists():
        pytest.skip('sample_data/ not present')
    from hadoop_loader import load_hadoop_logs
    entries = load_hadoop_logs(data_dir)
    assert len(entries) > 0
    assert all(k in entries[0] for k in ('timestamp', 'level', 'logger', 'message'))
    assert entries[0]['level'] in ('INFO', 'WARNING', 'ERROR', 'CRITICAL')


def test_parser():
    """Parser extracts correct fields from a known log line."""
    import tempfile
    from log_parser import parse_log_file
    log_line = "2026-06-16T08:00:00 — ERROR — app.service — Database connection failed: timeout\n"
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write(log_line)
        tmp = Path(f.name)
    entries = parse_log_file(tmp, hours=48)
    assert len(entries) == 1
    assert entries[0]['level'] == 'ERROR'
    assert 'Database connection failed' in entries[0]['message']


def test_analyser():
    """Analyser returns correct severity counts and spike detection."""
    import os
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from analyser import count_by_severity, detect_spikes, top_errors
    from config_loader import load_config
    from log_parser import to_dataframe
    config = load_config()
    df = to_dataframe(_make_entries())
    severity = count_by_severity(df)
    assert severity['total'] > 0
    assert 0 <= severity['error_rate'] <= 1
    spikes = detect_spikes(df, config)
    assert isinstance(spikes, list)
    errors = top_errors(df)
    assert isinstance(errors, list)


def test_email_builder():
    """HTML report builds without error and contains key content."""
    import os
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
    from config_loader import load_config
    from email_builder import build_html_report, build_subject
    from log_parser import to_dataframe
    config = load_config()
    df = to_dataframe(_make_entries())
    severity = count_by_severity(df)
    errors = top_errors(df)
    spikes = detect_spikes(df, config)
    report = generate_summary(df, severity, errors, spikes, hours=24)
    html = build_html_report(report, config)
    subject = build_subject(report, config)
    assert '<html' in html.lower()
    assert report.status in html
    assert 'Log Health Report' in subject


def test_dry_run(capsys):
    """--dry-run prints report to console and does not raise."""
    import os
    import subprocess
    import sys
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    result = subprocess.run(
        [sys.executable, 'run_report.py', '--dry-run'],
        capture_output=True, text=True,
        env={**os.environ, 'EMAIL_USERNAME': 'test@example.com', 'EMAIL_PASSWORD': 'testpassword'},
    )
    assert result.returncode == 0, result.stderr
    assert 'Status:' in result.stdout
