# Morning health check script.
# Reads Hadoop logs, analyses them, and emails an HTML report to the team.
#
# Usage:
#   python run_report.py            # analyse, email
#   python run_report.py --dry-run  # print report to console, do not email

import argparse
import sys
from pathlib import Path

from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
from config_loader import load_config, validate_config
from email_builder import build_html_report, build_subject
from email_sender import _build_plain_text_fallback, send_report
from hadoop_loader import load_hadoop_logs
from log_parser import to_dataframe


def parse_args():
    parser = argparse.ArgumentParser(
        description='Log health check — analyses Hadoop logs and emails an HTML report.'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print the report to console instead of sending email.'
    )
    parser.add_argument(
        '--config', type=Path, default=Path('config.yaml'),
        help='Path to config file (default: config.yaml)'
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # Step 1: load and validate config
    config = load_config(args.config)
    validate_config(config)

    # Step 2: load real Hadoop logs
    data_dir = Path('sample_data')
    if not data_dir.exists():
        print("Error: sample_data/ not found.", file=sys.stderr)
        sys.exit(1)
    entries = load_hadoop_logs(data_dir)
    print(f"Loaded {len(entries)} entries from Hadoop logs")

    # Step 3: convert to DataFrame
    df = to_dataframe(entries)
    hours = max(1, int((df['timestamp'].max() - df['timestamp'].min()).total_seconds() / 3600))

    # Step 5: run all analyses
    severity  = count_by_severity(df)
    top_errs  = top_errors(df, n=config['analysis']['top_errors_n'])
    spikes    = detect_spikes(df, config)

    # Step 6: generate LogReport
    report = generate_summary(df, severity, top_errs, spikes, hours=hours)
    print(repr(report))

    # Step 7: build HTML email and subject
    html    = build_html_report(report, config)
    subject = build_subject(report, config)

    # Step 8: dry-run or send
    if args.dry_run:
        print('\n' + '=' * 60)
        print(_build_plain_text_fallback(report))
        print('=' * 60)
        print(f'\nSubject: {subject}')
        sys.exit(0)

    # Step 9: send email
    success = send_report(html, subject, config)
    if not success:
        sys.exit(1)
