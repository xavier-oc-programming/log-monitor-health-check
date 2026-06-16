import json
import os
from datetime import datetime, timedelta
from pathlib import Path


_PROJECT_ROOT = Path(__file__).parent.parent


def _make_config():
    os.environ.setdefault('EMAIL_USERNAME', 'test@example.com')
    os.environ.setdefault('EMAIL_PASSWORD', 'testpassword')
    from config_loader import load_config
    return load_config(config_path=_PROJECT_ROOT / 'config.yaml', require_smtp=False)


def _make_spike(rate=0.11, severity='critical'):
    return {
        'window':        '2015-10-18 21:40:00',
        'total_entries': 1338,
        'error_count':   149,
        'error_rate':    rate,
        'severity':      severity,
    }


def _make_severity():
    return {'INFO': 168920, 'WARNING': 11438, 'ERROR': 521, 'CRITICAL': 17,
            'DEBUG': 0, 'total': 180896, 'error_rate': 0.003, 'warning_rate': 0.063}


def _make_top_errs():
    return [{'message_prefix': 'ERROR IN CONTACTING RM.', 'count': 480, 'pct_of_errors': 0.89}]


# --- payload structure ---

def test_payload_critical_structure():
    from slack_sender import build_payload
    config = _make_config()
    payload = build_payload('CRITICAL', 'WARNING', _make_spike(), _make_top_errs(), _make_severity(), config)
    assert 'attachments' in payload
    att = payload['attachments'][0]
    assert att['color'] == '#EF4444'
    blocks = att['blocks']
    header = next(b for b in blocks if b['type'] == 'header')
    assert 'CRITICAL' in header['text']['text']


def test_payload_warning_colour():
    from slack_sender import build_payload
    config = _make_config()
    payload = build_payload('WARNING', 'HEALTHY', _make_spike(rate=0.06, severity='warning'), _make_top_errs(), _make_severity(), config)
    assert payload['attachments'][0]['color'] == '#F59E0B'


def test_payload_recovery():
    from slack_sender import build_payload
    config = _make_config()
    payload = build_payload('HEALTHY', 'CRITICAL', None, [], _make_severity(), config)
    att = payload['attachments'][0]
    assert att['color'] == '#22C55E'
    text = json.dumps(att['blocks'])
    assert 'recovered' in text.lower()


def test_payload_contains_spike_fields():
    from slack_sender import build_payload
    config = _make_config()
    payload = build_payload('CRITICAL', 'HEALTHY', _make_spike(), _make_top_errs(), _make_severity(), config)
    text = json.dumps(payload)
    assert '11%' in text or '0.11' in text or '149' in text
    assert 'ERROR IN CONTACTING RM' in text


def test_payload_contains_context_link():
    from slack_sender import build_payload
    config = _make_config()
    payload = build_payload('WARNING', 'HEALTHY', _make_spike(rate=0.06, severity='warning'), [], _make_severity(), config)
    text = json.dumps(payload)
    assert 'log-monitor-health-check' in text


# --- state transitions ---

def test_state_transition_fires(tmp_path, monkeypatch):
    """Alert fires when status changes."""
    monkeypatch.chdir(tmp_path)
    alerts = []

    import run_alert
    monkeypatch.setattr(run_alert, 'load_hadoop_logs', lambda _: _fake_entries_with_spike())
    monkeypatch.setattr(run_alert, 'send_alert', lambda payload, url: alerts.append(payload))
    monkeypatch.setenv('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/fake')

    config = _make_config()
    # Start HEALTHY, run with spike data → should transition to WARNING/CRITICAL
    status = run_alert.check(config, dry_run=False)
    assert status in ('WARNING', 'CRITICAL')
    assert len(alerts) == 1


def test_state_no_alert_on_same_status(tmp_path, monkeypatch):
    """No alert fires when status is unchanged."""
    monkeypatch.chdir(tmp_path)
    alerts = []

    import run_alert
    monkeypatch.setattr(run_alert, 'load_hadoop_logs', lambda _: _fake_entries_with_spike())
    monkeypatch.setattr(run_alert, 'send_alert', lambda payload, url: alerts.append(payload))
    monkeypatch.setenv('SLACK_WEBHOOK_URL', 'https://hooks.slack.com/fake')

    config = _make_config()
    run_alert.check(config, dry_run=False)   # first check — fires alert
    alerts.clear()
    run_alert.check(config, dry_run=False)   # second check — same status, silent
    assert len(alerts) == 0


def test_dry_run_prints_payload(tmp_path, monkeypatch, capsys):
    """--dry-run prints JSON payload without POSTing."""
    monkeypatch.chdir(tmp_path)
    posted = []

    import run_alert
    monkeypatch.setattr(run_alert, 'load_hadoop_logs', lambda _: _fake_entries_with_spike())
    monkeypatch.setattr(run_alert, 'send_alert', lambda payload, url: posted.append(payload))

    config = _make_config()
    run_alert.check(config, dry_run=True)

    captured = capsys.readouterr()
    assert 'attachments' in captured.out
    assert len(posted) == 0


# --- helpers ---

def _fake_entries_with_spike():
    """Create entries that produce a detectable spike without real log files."""
    base = datetime(2015, 10, 18, 21, 40, 0)
    entries = []
    # 100 INFO entries spread over the hour
    for i in range(100):
        entries.append({
            'timestamp': base - timedelta(minutes=60) + timedelta(seconds=i * 36),
            'level': 'INFO', 'logger': 'Test', 'message': 'info msg', 'raw': '',
        })
    # 15 ERROR entries in a single 5-minute window — error rate 15/25 = 60%
    for i in range(15):
        entries.append({
            'timestamp': base + timedelta(seconds=i * 10),
            'level': 'ERROR', 'logger': 'Test', 'message': 'ERROR IN CONTACTING RM.', 'raw': '',
        })
    # 10 INFO entries in the same window
    for i in range(10):
        entries.append({
            'timestamp': base + timedelta(seconds=150 + i * 10),
            'level': 'INFO', 'logger': 'Test', 'message': 'info msg', 'raw': '',
        })
    return entries
