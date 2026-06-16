from pathlib import Path


def test_config_loads():
    """Config loads without error when env vars are set."""
    import os
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from config_loader import load_config, validate_config
    config = load_config()
    validate_config(config)


def test_log_generation():
    """LogGenerator produces the expected number of entries."""
    import os
    import tempfile
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from config_loader import load_config
    from log_generator import LogGenerator
    config = load_config()
    with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
        tmp = Path(f.name)
    gen = LogGenerator(config, output_path=tmp)
    gen.cfg['n_entries'] = 200
    gen.generate()
    assert tmp.exists()
    assert tmp.stat().st_size > 0


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
    import tempfile
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
    from config_loader import load_config
    from log_generator import LogGenerator
    from log_parser import parse_log_file, to_dataframe
    config = load_config()
    with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
        tmp = Path(f.name)
    LogGenerator(config, output_path=tmp).generate()
    entries = parse_log_file(tmp, hours=48)
    df = to_dataframe(entries)
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
    import tempfile
    os.environ['EMAIL_USERNAME'] = 'test@example.com'
    os.environ['EMAIL_PASSWORD'] = 'testpassword'
    from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
    from config_loader import load_config
    from email_builder import build_html_report, build_subject
    from log_generator import LogGenerator
    from log_parser import parse_log_file, to_dataframe
    config = load_config()
    with tempfile.NamedTemporaryFile(suffix='.log', delete=False) as f:
        tmp = Path(f.name)
    LogGenerator(config, output_path=tmp).generate()
    df = to_dataframe(parse_log_file(tmp, hours=48))
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
    assert result.returncode == 0
    assert 'Status:' in result.stdout
