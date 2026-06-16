from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_report():
    response = client.get('/api/report')
    assert response.status_code in [200, 503]
    if response.status_code == 200:
        data = response.json()
        assert 'status' in data
        assert 'total_entries' in data
        assert 'error_rate_pct' in data
        assert data['status'] in ['HEALTHY', 'WARNING', 'CRITICAL']


def test_severity_counts():
    response = client.get('/api/severity-counts')
    assert response.status_code in [200, 503]


def test_top_errors():
    response = client.get('/api/top-errors')
    assert response.status_code in [200, 503]


def test_spikes():
    response = client.get('/api/spikes')
    assert response.status_code in [200, 503]


def test_plot_served():
    response = client.get('/plots/error_timeline.png')
    assert response.status_code in [200, 404]


def test_plot_blocked():
    response = client.get('/plots/../../etc/passwd')
    assert response.status_code == 404


def test_analyser_directly():
    """Test the analyser without the API layer."""
    import os
    from datetime import datetime, timedelta

    from analyser import count_by_severity, detect_spikes, top_errors
    from config_loader import load_config
    from log_parser import to_dataframe

    os.environ.setdefault('EMAIL_USERNAME', 'test@example.com')
    os.environ.setdefault('EMAIL_PASSWORD', 'testpassword')

    config = load_config(require_smtp=False)
    now = datetime(2015, 10, 18, 10, 0, 0)
    entries = [
        {'timestamp': now + timedelta(seconds=i), 'level': lvl,
         'logger': 'Test', 'message': f'{lvl} msg', 'raw': ''}
        for i, lvl in enumerate(['INFO'] * 50 + ['WARNING'] * 10 + ['ERROR'] * 5)
    ]
    df = to_dataframe(entries)

    assert len(df) > 0
    severity = count_by_severity(df)
    assert severity['total'] > 0
    assert 0 <= severity['error_rate'] <= 1
    assert isinstance(top_errors(df, n=5), list)
    assert isinstance(detect_spikes(df, config), list)
