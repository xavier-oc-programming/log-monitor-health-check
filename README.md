# log-monitor-health-check

A Python morning health check script that reads application logs, analyses them for errors and anomaly spikes, and emails an HTML report to the team. Scheduled via GitHub Actions cron to run at 08:00 UTC daily — the same pattern used in corporate IT environments where a script runs before the team arrives and the inbox tells them whether anything needs attention. The script is self-contained: it generates its own synthetic logs so it runs anywhere without needing a real application. Pass `--log-file` to point it at real logs instead. Part 1 of a four-part log monitoring series.

[GitHub](https://github.com/xavier-oc-programming/log-monitor-health-check) &nbsp;|&nbsp;
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![pandas](https://img.shields.io/badge/pandas-2.0+-150458?logo=pandas)
![smtplib](https://img.shields.io/badge/smtplib-stdlib-green)
![PyYAML](https://img.shields.io/badge/PyYAML-6.0+-red)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-cron-2088FF?logo=github-actions)
![pytest](https://img.shields.io/badge/pytest-7.0+-0A9EDC?logo=pytest)

---

## 0. Prerequisites

Python 3.11+. Gmail account with App Password enabled (or any SMTP server). No cloud account required.

---

## 1. Quick start

```bash
git clone https://github.com/xavier-oc-programming/log-monitor-health-check
cd log-monitor-health-check
pip install -r requirements.txt
cp config.yaml.example config.yaml
cp .env.example .env                 # fill in your credentials
source .env                          # load env vars into current shell
python run_report.py --dry-run       # preview report without sending
python run_report.py                 # generate logs, analyse, send email
```

---

## 2. Project structure

```
log-monitor-health-check/
├── .env.example            # committed — template for local env vars
├── .env                    # gitignored — real credentials, never committed
├── config.yaml.example     # committed — safe config template, no credentials
├── config.yaml             # gitignored — local config copy
├── config_loader.py        # loads config.yaml, merges all env vars
├── log_generator.py        # LogGenerator class — produces synthetic logs
├── log_parser.py           # regex parser, returns structured entries
├── analyser.py             # severity counts, spike detection, LogReport
├── email_builder.py        # builds self-contained HTML email body
├── email_sender.py         # sends report via smtplib STARTTLS
├── run_report.py           # main entry point — CLI argument handling
├── conftest.py             # adds project root to sys.path for pytest
├── README.md
├── requirements.txt
├── portfolio.yaml
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml          # two jobs: test (every push) + run_report (cron)
├── tests/
│   └── test_report.py      # five end-to-end tests covering each module
└── logs/                   # gitignored — generated at runtime
    └── app.log
```

---

## 3. Core concepts

**Why morning health check scripts exist.** In banks and large IT organisations, automated scripts run overnight and at the start of the business day. The team arrives, opens their inbox, and the email tells them whether anything needs attention — without anyone having to query a dashboard. This pattern is valuable because it is asynchronous, auditable, and requires no login. The report becomes a timestamped record of system state.

**Log severity levels in practice.** DEBUG is internal developer noise: cache hits, query times, config loads. INFO is normal operational events: requests completed, jobs finished, users authenticated. WARNING signals something degraded but not broken: elevated latency, high memory usage, retry attempts. ERROR means a specific operation failed: a database connection dropped, a file was not found, a request returned 5xx. CRITICAL means the system itself is impaired: the connection pool is exhausted, a service is unresponsive, data corruption has been detected.

**Regex parsing vs structured logging.** This script uses regex against plain-text log lines, which is how most legacy applications and many open-source tools write logs. Structured logging (JSON lines) is cleaner — each field is already typed and named — but it requires the application to be configured for it. Regex parsing works on any log file without touching the application. The trade-off is fragility: if the log format changes, the pattern breaks silently. Production teams typically keep both: regex parsing for legacy systems, structured ingestion for new services.

**5-minute window anomaly detection.** The analyser groups entries into 5-minute buckets and computes the error rate for each. A window is flagged if its error rate exceeds the configured threshold. Thresholding on rate rather than raw count is scale-invariant: 5 errors out of 10 entries is far more alarming than 10 errors out of 500 entries, even though the raw count is higher. The 5-minute window is narrow enough to catch deployment failures and traffic surges, and wide enough to avoid flagging isolated transient errors.

**Message prefix grouping.** Variable substitution makes each log occurrence look unique: `"Database connection failed: timeout"` and `"Database connection failed: SSL error"` are different strings but the same underlying problem. Grouping by the first 60 characters collapses these variants into a single count. Production tools like Datadog and Splunk use ML clustering for the same reason; prefix truncation is the lightweight equivalent that works without a model.

**STARTTLS vs plain SMTP.** Port 25 is the legacy plain-text SMTP port, blocked by most ISPs and cloud providers. Port 587 with STARTTLS is the standard for authenticated, encrypted email submission. The connection starts unencrypted, and `STARTTLS` upgrades it to TLS before credentials are sent — so the username and password are never transmitted in the clear. Port 465 (SMTPS) wraps the entire connection in TLS from the start; both are secure, but 587 with STARTTLS is the current standard.

**MIMEMultipart('alternative').** HTML email clients display the HTML part of a message. Older clients, terminal email readers, and some corporate mail gateways display plain text. `MIMEMultipart('alternative')` packages both versions into one message and tells clients to render whichever they support, preferring HTML. Using `'mixed'` instead would cause some clients to display the HTML as an attachment rather than inline.

**Gmail App Passwords.** Google requires that scripts authenticating to Gmail use an App Password — a 16-character token generated in Account Settings — rather than the account password. This is because the account password triggers 2FA, which a script cannot complete. App Passwords bypass 2FA for a specific application, can be revoked individually, and are scoped so revoking one does not affect other sessions.

---

## 4. Configuration

All credentials and personal addresses come from environment variables — nothing sensitive is ever stored in a committed file. `config.yaml` controls runtime behaviour (SMTP host, analysis thresholds, log generation settings) and is gitignored. Copy `config.yaml.example` to `config.yaml` to get started; the defaults work without any edits.

`.env` holds the four environment variables the script needs. Copy `.env.example` to `.env`, fill in your values, and run `source .env` before running the script. `.env` is gitignored and will never be committed. For GitHub Actions, the same four variables are stored as repository secrets.

```
EMAIL_USERNAME   — Gmail address used to authenticate with SMTP
EMAIL_PASSWORD   — Gmail App Password (16-character token, not your account password)
EMAIL_TO         — recipient address for the report
EMAIL_FROM       — sender address shown in the From field
```

`config_loader.py` always reads these four from the environment at load time, overwriting any values present in `config.yaml`. This means even if `config.yaml` is accidentally filled in with real addresses, the environment variables take precedence.

```yaml
# config.yaml.example

smtp:
  host: smtp.gmail.com
  port: 587
  username: ""    # set via EMAIL_USERNAME environment variable
  password: ""    # set via EMAIL_PASSWORD environment variable

email:
  from: "Log Monitor <your_email@gmail.com>"
  to:
    - recipient@example.com
  subject_prefix: "Log Health Report"

analysis:
  default_hours: 24              # analyse logs from the past N hours
  error_rate_threshold: 0.10     # flag windows above 10% error rate
  spike_window_minutes: 5
  top_errors_n: 10
  spike_start_entry: 800         # artificial spike start
  spike_end_entry: 900           # artificial spike end
  spike_error_prob: 0.40         # ERROR probability inside spike window

log_generation:
  n_entries: 2000
  seed: 42
  severity_weights:
    DEBUG: 0.20
    INFO: 0.55
    WARNING: 0.15
    ERROR: 0.08
    CRITICAL: 0.02
```

The `analysis.spike_*` fields configure the artificial anomaly injected into synthetic logs. Entries 800–900 have a 40% probability of being `ERROR` rather than the normal 8%. This makes the spike detection reliably trigger on every run, demonstrating the feature without needing a real incident.

---

## 5. How it works

`run_report.py` is the entry point. It reads the CLI arguments, loads config, determines the log source, runs the analysis pipeline, builds the email, and either prints to the console (`--dry-run`) or sends via SMTP.

`log_generator.py` contains `LogGenerator`, which produces 2,000 synthetic log entries spanning the past 24 hours. Timestamps are distributed with random exponential gaps rather than even spacing, simulating real activity bursts. Between entries 800 and 900, the ERROR probability is raised to 40%, creating a sharp, detectable spike. The generator writes to `logs/app.log` and returns the path.

`log_parser.py` applies a regex pattern to each line and returns structured dicts filtered to the configured time window. Malformed lines are skipped silently. `to_dataframe()` converts the list to a pandas DataFrame and adds three derived columns: `hour`, `minute_window` (floored to 5-minute intervals), and `is_error`.

`analyser.py` contains four standalone functions and the `LogReport` class. `count_by_severity()` counts entries by level and computes error and warning rates. `top_errors()` groups ERROR and CRITICAL messages by their first 60 characters and returns the most frequent. `detect_spikes()` groups the DataFrame by `minute_window` and flags buckets where the error rate exceeds the threshold. `generate_summary()` combines all results into a `LogReport` and determines overall status.

`email_builder.py` builds the HTML report string from a `LogReport`. All CSS is inline — no external stylesheets, no `<style>` tags — because email clients strip both. The layout is built with nested HTML tables rather than CSS flexbox or grid, because Outlook does not support modern CSS layout.

`email_sender.py` connects to the configured SMTP host, upgrades to TLS via STARTTLS, authenticates with the environment-sourced credentials, and sends a `MIMEMultipart('alternative')` message containing both plain text and HTML parts. If sending fails for any reason, it logs the error and returns `False` rather than raising — a failed send should not crash a scheduled script.

---

## 6. The HTML report

The report is a self-contained HTML document with a fixed 700px maximum width, centred on a light grey background. The header is dark navy (`#1E293B`) with white text. Below it, a full-width status banner is coloured green, amber, or red depending on whether the system is HEALTHY, WARNING, or CRITICAL. Four metric cards show total entries, error rate, anomaly spike count, and the date. A severity breakdown table lists all five levels with their counts and percentages, each row colour-coded with a left border. The top errors table groups by message prefix. The anomaly spikes section shows one card per detected window with a severity badge. The recommendations section lists plain-English actions on an amber background. The footer links to the GitHub repo. All colours are from a consistent palette; all font sizing is explicit so clients cannot override it.

---

## 7. Sample output

`--dry-run` prints the plain text fallback to the console:

```
LOG HEALTH REPORT — 2026-06-16 08:00:01
Status: WARNING
Entries: 2000 over 24h
Error rate: 12.4%
Spikes: 2

TOP ERRORS:
  1. Database connection failed (47)
  2. Timeout after connecting to (31)
  3. Request failed: POST /api/predict (28)

RECOMMENDATIONS:
  - Error rate is 12.4% — above the 10% threshold. Most frequent error: 'Database connection failed'.
  - Anomaly spike at 2026-06-16 07:35: 38 errors in 5 minutes (40% error rate). Investigate what changed at this time.
```

Sample `LogReport.__repr__`:
```
LogReport(status='WARNING', total_entries=2000, spike_count=2, error_rate_pct=12.4%)
```

Sample subject lines:
```
Log Health Report — ✓ HEALTHY — 2026-06-16
Log Health Report — ⚠ WARNING — 2026-06-16 — 1 anomaly spike
Log Health Report — ✗ CRITICAL — 2026-06-16 — 3 anomaly spikes
```

---

## 9. Scheduling

**GitHub Actions.** The `ci.yml` workflow includes a `schedule` trigger with the cron expression `0 8 * * *`, which fires at 08:00 UTC every day. The `run_report` job runs only on this trigger (not on push or PR). It requires `EMAIL_USERNAME` and `EMAIL_PASSWORD` to be set as repository secrets. To trigger the scheduled run manually: go to the Actions tab, select the CI workflow, and click "Run workflow".

**Windows Task Scheduler.** To schedule the script locally on Windows:
```
schtasks /create /tn "LogHealthCheck" /tr "python C:\path\to\run_report.py" /sc DAILY /st 08:00
```

**Linux / macOS cron.** Add to crontab with `crontab -e`:
```
0 8 * * * cd /path/to/log-monitor-health-check && python run_report.py
```

---

## 10. Deployment

This is a script, not a web application — no cloud deployment is required. The production deployment is the GitHub Actions cron schedule. To set it up: fork or clone the repo to your GitHub account, add all four secrets (`EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_TO`, `EMAIL_FROM`) under Settings → Secrets and variables → Actions, then push to `main`. The first scheduled run will occur at 08:00 UTC. Monitor the Actions tab to confirm the run completed and the report was sent. The run history is public and timestamped, providing an audit trail of every morning check.

---

## 11. CI/CD — GitHub Actions

The workflow contains two jobs. The `test` job runs on every push and pull request to `main`. It installs dependencies, sets dummy environment variables (`EMAIL_USERNAME=test@example.com`, `EMAIL_PASSWORD=testpassword`), and runs `pytest tests/ -v`. All five tests run without real SMTP credentials because `test_dry_run` passes `--dry-run`, and the other tests exercise the analysis pipeline only. The `run_report` job runs only when the `schedule` event fires — it is the production deployment.

To configure secrets for the scheduled run:
```bash
gh secret set EMAIL_USERNAME --body "your@gmail.com" --repo xavier-oc-programming/log-monitor-health-check
gh secret set EMAIL_PASSWORD --body "your_app_password" --repo xavier-oc-programming/log-monitor-health-check
gh secret set EMAIL_TO       --body "your@gmail.com"   --repo xavier-oc-programming/log-monitor-health-check
gh secret set EMAIL_FROM     --body "your@gmail.com"   --repo xavier-oc-programming/log-monitor-health-check
```
The App Password is generated in Google Account → Security → 2-Step Verification → App passwords. Use a dedicated Gmail account for script automation rather than a personal account.

---

## 12. Design decisions

`LogGenerator` is a class because it has shared mutable state that multiple methods need to access on every call: the seeded `Random` instance and the generation configuration. A seeded `random.Random` instance is used rather than calling `random.seed()` globally because global seed state is process-wide — if two generators with different seeds were created in the same test run, the second `seed()` call would overwrite the first, making results non-reproducible. Instance-level `Random` objects are independent. The class also makes it straightforward to swap in a different output path in tests without touching the config.

`LogReport` is a plain class rather than a dataclass or a dict because it gives the analyser and email builder a clear, typed contract with named attributes and a useful `__repr__` for debugging, without requiring a decorator. A `@dataclass` would work, but the spec prohibits decorators on either class. A dict would make the interface implicit — callers would need to know the key names rather than reading a typed signature. No `to_dict()` method is needed because there is no API layer; the `LogReport` flows directly from `generate_summary()` into `build_html_report()` and `build_subject()`.

The `--dry-run` flag exists because the analysis logic and the email-sending logic are entirely separate, and testing them together requires real SMTP credentials. By printing the plain text fallback to the console, `--dry-run` lets the entire pipeline — log generation, parsing, analysis, HTML build, subject build — be exercised in CI without any network calls. This mirrors how real automation scripts handle test versus production modes: the logic runs identically in both environments, and only the output destination differs.

---

## 13. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | >=2.0 | Log aggregation, severity counts, spike detection |
| numpy | >=1.24,<2.0 | Numerical support for pandas |
| pyyaml | >=6.0 | Loading config.yaml |
| pytest | >=7.0 | Test runner |
| smtplib | stdlib | SMTP email sending |
| email.mime | stdlib | MIME message construction |
| re | stdlib | Log line regex parsing |
| argparse | stdlib | CLI argument handling |
| pathlib | stdlib | Cross-platform file paths |
| collections | stdlib | Counter, defaultdict |
| logging | stdlib | Runtime logging |
