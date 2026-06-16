# Morning health check script.
# Reads logs, analyses them, and emails an HTML report to the team.
#
# Usage:
#   python run_report.py                    # generate synthetic logs, analyse, email
#   python run_report.py --hours 12         # analyse last 12 hours only
#   python run_report.py --log-file app.log # read a real log file
#   python run_report.py --dry-run          # print report to console, do not email
#   python run_report.py --no-generate      # skip log generation, use existing logs

import argparse
import sys
from pathlib import Path

from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
from config_loader import load_config, validate_config
from email_builder import build_html_report, build_subject
from email_sender import _build_plain_text_fallback, send_report
from log_generator import LogGenerator
from log_parser import parse_log_file, to_dataframe


def parse_args():
    parser = argparse.ArgumentParser(
        description='Morning log health check — analyses logs and emails an HTML report.'
    )
    parser.add_argument(
        '--hours', type=int, default=None,
        help='Number of hours to analyse (default: from config.yaml)'
    )
    parser.add_argument(
        '--log-file', type=Path, default=None,
        help='Path to an existing log file. If not provided, synthetic logs are generated.'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Print the report to console instead of sending email. Useful for testing.'
    )
    parser.add_argument(
        '--no-generate', action='store_true',
        help='Skip log generation and use existing logs/app.log.'
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

    # Step 2: determine log source
    if args.log_file:
        log_path = args.log_file
        if not log_path.exists():
            print(f"Error: log file not found: {log_path}", file=sys.stderr)
            sys.exit(1)
    elif args.no_generate:
        log_path = Path('logs/app.log')
        if not log_path.exists():
            print("Error: logs/app.log not found. Run without --no-generate to create it.", file=sys.stderr)
            sys.exit(1)
    else:
        log_path = LogGenerator(config).generate()
        print(f"Generated synthetic logs: {log_path}")

    # Step 3: parse log file
    hours = args.hours or config['analysis']['default_hours']
    entries = parse_log_file(log_path, hours=hours)
    print(f"Parsed {len(entries)} entries from the past {hours} hours")

    # Step 4: convert to DataFrame
    df = to_dataframe(entries)

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
