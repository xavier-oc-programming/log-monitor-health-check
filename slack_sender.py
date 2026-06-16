import json
import os
import urllib.request
from datetime import datetime


COLOURS = {
    'CRITICAL': '#EF4444',
    'WARNING':  '#F59E0B',
    'HEALTHY':  '#22C55E',
}

STATUS_EMOJI = {
    'CRITICAL': ':red_circle:',
    'WARNING':  ':large_yellow_circle:',
    'HEALTHY':  ':large_green_circle:',
}

TRANSITION_TEXT = {
    ('HEALTHY',   'WARNING'):  'Error rate elevated — anomaly spike detected.',
    ('HEALTHY',   'CRITICAL'): 'Critical anomaly detected — immediate attention required.',
    ('WARNING',   'CRITICAL'): 'Escalating — error rate crossed critical threshold.',
    ('CRITICAL',  'WARNING'):  'Partially recovered — still above warning threshold.',
    ('CRITICAL',  'HEALTHY'):  'System recovered — no anomaly spikes detected.',
    ('WARNING',   'HEALTHY'):  'System recovered — no anomaly spikes detected.',
}


def build_payload(
    new_status: str,
    prev_status: str,
    worst_spike: dict | None,
    top_errs: list,
    severity_counts: dict,
    config: dict,
) -> dict:
    """
    Build a Slack Block Kit payload for a status transition.

    Uses the attachments API for the coloured sidebar — Block Kit alone
    cannot produce a left border colour on messages.
    """
    emoji = STATUS_EMOJI[new_status]
    colour = COLOURS[new_status]
    transition = TRANSITION_TEXT.get((prev_status, new_status), f'{prev_status} → {new_status}')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    fields = []
    if worst_spike:
        fields += [
            {'type': 'mrkdwn', 'text': f"*Worst window:*\n{str(worst_spike['window'])[:-3]}"},
            {'type': 'mrkdwn', 'text': f"*Error rate:*\n{worst_spike['error_rate']:.0%} (threshold: {int(config['analysis']['error_rate_threshold']*100)}%)"},
            {'type': 'mrkdwn', 'text': f"*Errors in window:*\n{worst_spike['error_count']:,} / {worst_spike['total_entries']:,} entries"},
        ]
    if top_errs:
        fields.append({'type': 'mrkdwn', 'text': f"*Top error:*\n`{top_errs[0]['message_prefix'][:60]}`"})

    blocks = [
        {
            'type': 'header',
            'text': {'type': 'plain_text', 'text': f"{emoji} {new_status} — Log Monitor", 'emoji': True},
        },
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': transition},
        },
    ]

    if fields:
        blocks.append({'type': 'section', 'fields': fields})

    blocks.append({
        'type': 'context',
        'elements': [{'type': 'mrkdwn', 'text': f"{now} · <https://github.com/xavier-oc-programming/log-monitor-health-check|log-monitor-health-check>"}],
    })

    return {
        'attachments': [{
            'color': colour,
            'blocks': blocks,
        }]
    }


def send_alert(payload: dict, webhook_url: str) -> bool:
    """
    POST the payload to the Slack webhook URL.
    Returns True on success, False on failure.
    """
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as exc:
        print(f"Slack alert failed: {exc}")
        return False
