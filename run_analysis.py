# Orchestration script — generates a fresh log file and runs the full analysis pipeline.
# python run_analysis.py
# Outputs: logs/app.log, reports/latest_report.json, plots/*.png
# The FastAPI app serves the saved report — run this script before starting main.py.

import json
from pathlib import Path

from analyser import count_by_severity, detect_spikes, generate_summary, hourly_breakdown, top_errors
from config_loader import load_config, validate_config
from log_generator import LogGenerator
from log_parser import parse_log_file, to_dataframe
from visualise import generate_all_plots


def run() -> dict:
    config = load_config(require_smtp=False)
    validate_config(config, require_smtp=False)

    Path('logs').mkdir(exist_ok=True)
    Path('reports').mkdir(exist_ok=True)
    Path('plots').mkdir(exist_ok=True)

    log_path = LogGenerator(config).generate()
    print(f"Generated: {log_path}")

    hours = config['analysis']['default_hours']
    entries = parse_log_file(log_path, hours=hours)
    print(f"Parsed {len(entries)} entries")

    df = to_dataframe(entries)

    severity  = count_by_severity(df)
    top_errs  = top_errors(df, n=config['analysis']['top_errors_n'])
    spikes    = detect_spikes(df, config)
    hourly    = hourly_breakdown(df)
    report    = generate_summary(df, severity, top_errs, spikes, hours=hours)

    threshold   = config['analysis']['error_rate_threshold']
    min_entries = config['analysis'].get('min_window_entries', 10)
    generate_all_plots(df, severity, hourly, spikes, top_errs,
                       threshold=threshold, min_entries=min_entries)
    print("Plots generated")

    report_path = Path('reports/latest_report.json')
    report_path.write_text(json.dumps(report.to_dict(), default=str))
    print(f"Report saved: {report_path}")

    print(f"\n{repr(report)}")
    print(f"Status: {report.status} — {report.status_reason}")
    for rec in report.recommendations:
        print(f"  • {rec}")

    return report.to_dict()


if __name__ == '__main__':
    run()
