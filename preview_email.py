# Opens the HTML email report in your default browser for visual testing.
# python preview_email.py
# No SMTP credentials needed — just generates and opens the HTML locally.

import webbrowser
from pathlib import Path

from analyser import count_by_severity, detect_spikes, generate_summary, top_errors
from config_loader import load_config
from email_builder import build_html_report, build_subject
from log_generator import LogGenerator
from log_parser import parse_log_file, to_dataframe

if __name__ == '__main__':
    config = load_config(require_smtp=False)

    log_path = LogGenerator(config).generate()
    hours    = config['analysis']['default_hours']
    entries  = parse_log_file(log_path, hours=hours)
    df       = to_dataframe(entries)
    severity = count_by_severity(df)
    top_errs = top_errors(df, n=config['analysis']['top_errors_n'])
    spikes   = detect_spikes(df, config)
    report   = generate_summary(df, severity, top_errs, spikes, hours=hours)

    html    = build_html_report(report, config)
    subject = build_subject(report, config)

    out = Path('/tmp/email_preview.html')
    out.write_text(html)

    print(f"Subject: {subject}")
    print(f"Report:  {repr(report)}")
    print(f"Opening: {out}")
    webbrowser.open(f'file://{out}')
