# Slack alert daemon with deduplication.
#
# Usage:
#   python run_alert.py          # run once and exit (CI / cron mode)
#   python run_alert.py --watch  # run every 5 minutes until killed (daemon mode)
#   python run_alert.py --dry-run  # print Slack payload to console, no POST

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from analyser import count_by_severity, detect_spikes, top_errors
from config_loader import load_config, validate_config
from hadoop_loader import load_hadoop_logs
from log_parser import to_dataframe
from slack_sender import build_payload, send_alert

STATE_PATH = Path('state.json')


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {'status': 'HEALTHY'}


def save_state(status: str, spike: dict | None) -> None:
    STATE_PATH.write_text(json.dumps({
        'status':     status,
        'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'spike':      spike,
    }, default=str))


def check(config: dict, dry_run: bool = False) -> str:
    """
    Load logs, detect spikes, compare to previous state.
    Fires a Slack alert only when status changes.
    Returns the new status string.
    """
    entries  = load_hadoop_logs(Path('sample_data'))
    df       = to_dataframe(entries)
    severity = count_by_severity(df)
    spikes   = detect_spikes(df, config)
    top_errs = top_errors(df, n=1)

    has_critical = any(s['severity'] == 'critical' for s in spikes)
    if has_critical:
        new_status  = 'CRITICAL'
        worst_spike = max(spikes, key=lambda s: s['error_rate'])
    elif spikes:
        new_status  = 'WARNING'
        worst_spike = max(spikes, key=lambda s: s['error_rate'])
    else:
        new_status  = 'HEALTHY'
        worst_spike = None

    prev        = load_state()
    prev_status = prev.get('status', 'HEALTHY')

    if new_status != prev_status:
        payload     = build_payload(new_status, prev_status, worst_spike, top_errs, severity, config)
        webhook_url = os.environ.get('SLACK_WEBHOOK_URL', '')

        if dry_run:
            print(json.dumps(payload, indent=2))
        elif webhook_url:
            send_alert(payload, webhook_url)
        else:
            print("SLACK_WEBHOOK_URL not set — skipping POST")

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {prev_status} → {new_status} — alert fired")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {new_status} — no change, silent")

    save_state(new_status, worst_spike)
    return new_status


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Log monitor Slack alerter — fires only when status changes.'
    )
    parser.add_argument('--watch',   action='store_true', help='Run every 5 minutes until killed.')
    parser.add_argument('--dry-run', action='store_true', help='Print Slack payload, do not POST.')
    parser.add_argument('--interval', type=int, default=300, help='Watch interval in seconds (default: 300).')
    parser.add_argument('--config',  type=Path, default=Path('config.yaml'))
    args = parser.parse_args()

    config = load_config(args.config, require_smtp=False)
    validate_config(config, require_smtp=False)

    if args.watch:
        print(f"Watching every {args.interval}s — Ctrl+C to stop")
        while True:
            check(config, dry_run=args.dry_run)
            time.sleep(args.interval)
    else:
        check(config, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
