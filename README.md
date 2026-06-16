# Log Monitor — Health Check & Anomaly Detection

A Python pipeline that ingests real Hadoop cluster logs, detects error spikes using statistical thresholding, and delivers results through two channels: a FastAPI dashboard with live charts, and a scheduled HTML email report.

The dataset is the [LogHub Hadoop corpus](https://github.com/logpai/loghub) — 180,896 real log entries from a YARN cluster running WordCount and PageRank jobs, with labeled failure scenarios including machine down, network disconnection, and disk full events.

---

## Dashboard

![Error Timeline](plots/error_timeline.png)

The error timeline is the centrepiece — 5-minute windows plotted over the full log range. Grey bars are normal activity. Red bars are windows where the error rate crossed the 5% threshold. The two genuine failure events are immediately visible.

---

## What it detects

The pipeline detected two real anomalies from the labeled dataset:

| Time | Errors | Total entries | Error rate | Severity | Failure type |
|---|---|---|---|---|---|
| 2015-10-18 18:05 | 253 | 3,899 | 6% | WARNING | Disk full |
| 2015-10-18 21:40 | 149 | 1,338 | 11% | CRITICAL | Machine down |

Overall error rate across 48 hours: **0.3%** — making both spikes 20–35x deviations from baseline.

---

## Charts

### Severity Distribution
![Severity Distribution](plots/severity_distribution.png)

Breakdown of all 180,896 entries by log level. INFO dominates at 93.4%, which is expected for a healthy cluster — the 0.3% overall error rate confirms that errors are genuinely rare outside the failure windows.

### Hourly Activity
![Hourly Activity](plots/hourly_activity.png)

Log volume by hour of day, stacked by severity. The spike hours (18:00 and 21:00) show elevated WARNING and ERROR volumes compared to surrounding baseline hours.

### Top Errors
![Top Errors](plots/top_errors.png)

Most frequent error message prefixes. `ERROR IN CONTACTING RM` (ResourceManager) accounts for 480 occurrences — 89% of all errors — which is the signature of the machine-down failure scenario where YARN containers lose contact with the cluster manager.

### Email Report
![Email Report](plots/email_preview.png)

The HTML email delivered by `run_report.py` on a schedule. Contains severity breakdown, top errors table, anomaly spike summary with severity badges, and plain-English recommendations. Renders correctly in Gmail, Outlook, and Apple Mail.

---

## Architecture

```
sample_data/           <- Real Hadoop cluster logs (180k entries, labeled failures)
    application_*/
        container_*.log

hadoop_loader.py       <- Parses Hadoop log format, maps WARN->WARNING / FATAL->CRITICAL
log_parser.py          <- to_dataframe(): adds hour, minute_window, is_error columns
analyser.py            <- count_by_severity(), detect_spikes(), generate_summary()
visualise.py           <- Four Matplotlib charts -> plots/*.png
email_builder.py       <- Self-contained HTML email with inline CSS

run_analysis.py        <- CLI: load -> parse -> analyse -> plot -> save JSON report
run_report.py          <- CLI: load -> analyse -> email (scheduled via GitHub Actions)
main.py                <- FastAPI app: serves dashboard + JSON API + plots
```

Two delivery paths from the same pipeline:

```
hadoop_loader -> to_dataframe -> analyser -> visualise
                                     |               |
                              run_report.py    run_analysis.py
                              (email report)   (dashboard data)
```

---

## Spike detection logic

```python
# For each 5-minute window with >= 10 entries:
error_rate = error_count / total_entries

if error_rate > 0.05:        # above 5% -> spike
    if error_rate >= 0.10:   # above 10% -> critical
        severity = 'critical'
    else:
        severity = 'warning'
```

Thresholding on **rate** rather than raw count makes detection scale-invariant: 149 errors in 1,338 entries (11%) is far more alarming than 149 errors spread across 180,896 entries (0.08%).

The `min_window_entries = 10` filter eliminates sparse windows — a window with 1 entry and 1 error produces a 100% error rate but carries no statistical weight.

---

## Dataset

**Source:** [LogHub — Hadoop](https://github.com/logpai/loghub) (Zenodo, CC BY 4.0)

**Contents:** YARN container logs from WordCount and PageRank jobs run on a multi-node cluster. Both normal runs and runs with injected failures are included.

**Labeled failure types:**
- Machine down — nodes become unreachable mid-job
- Network disconnection — inter-node communication fails
- Disk full — output directory writes fail

**Log format:**
```
2015-10-18 21:40:23,154 ERROR [IPC Server handler 5] org.apache.hadoop.ipc.Server: IPC Server handler 5 on 8020 ...
```

`hadoop_loader.py` maps Java log levels to standard severity names:

| Hadoop | Internal |
|---|---|
| INFO | INFO |
| WARN | WARNING |
| ERROR | ERROR |
| FATAL | CRITICAL |

The loader extracts the short class name (e.g. `Server` from `org.apache.hadoop.ipc.Server`) as the logger field, drops stack trace continuation lines, and sorts all entries by timestamp before returning.

---

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/health` | Service health check |
| GET | `/api/report` | Full analysis report as JSON |
| GET | `/api/severity-counts` | Entry counts by level |
| GET | `/api/top-errors` | Top error message prefixes |
| GET | `/api/spikes` | Detected anomaly spikes |
| POST | `/api/analyse` | Re-run full analysis pipeline |
| GET | `/plots/{filename}` | Serve a chart image |

---

## Running locally

**Requirements:** Python 3.11+

```bash
# 1. Clone and install
git clone https://github.com/xavier-oc-programming/log-monitor-health-check
cd log-monitor-health-check
pip install -r requirements.txt

# 2. Download the dataset (~48MB)
curl -L -o Hadoop.zip "https://zenodo.org/records/8196385/files/Hadoop.zip?download=1"
mkdir sample_data && unzip Hadoop.zip -d sample_data && rm Hadoop.zip

# 3. Copy config
cp config.yaml.example config.yaml

# 4. Run the analysis pipeline (generates plots and report)
python run_analysis.py

# 5. Start the dashboard
uvicorn main:app --reload
# -> http://localhost:8000
```

**Email report (dry run — no SMTP needed):**
```bash
export EMAIL_USERNAME=you@gmail.com
export EMAIL_PASSWORD=your-app-password
python run_report.py --dry-run
```

**Preview the email HTML in your browser:**
```bash
python preview_email.py
```

---

## Configuration

`config.yaml.example` (copy to `config.yaml` — never commit this file):

```yaml
analysis:
  error_rate_threshold: 0.05   # windows above this are flagged as spikes
  spike_window_minutes: 5      # aggregation window size in minutes
  min_window_entries: 10       # ignore windows with fewer entries than this
  top_errors_n: 10             # number of top errors to surface
```

All SMTP credentials come from environment variables — never from the config file:

```bash
export EMAIL_USERNAME=your@gmail.com
export EMAIL_PASSWORD=your-app-password
export EMAIL_TO=recipient@example.com
export EMAIL_FROM="Log Monitor <your@gmail.com>"
```

---

## CI/CD

Three GitHub Actions jobs in `.github/workflows/ci.yml`:

| Job | Trigger | What it does |
|---|---|---|
| `test` | Every push and PR | Runs `pytest tests/ -v` (14 tests) |
| `run_report` | Daily cron 08:00 UTC | Downloads dataset, runs analysis, sends email |
| `deploy` | Push to main | Zips app and deploys to Azure App Service via Kudu zipdeploy |

Required GitHub secrets: `EMAIL_USERNAME`, `EMAIL_PASSWORD`, `EMAIL_TO`, `EMAIL_FROM`, `AZURE_CREDENTIALS`, `AZURE_APP_NAME`.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Data processing | pandas |
| Charts | Matplotlib |
| API | FastAPI + Uvicorn |
| Email | smtplib (STARTTLS, port 587) |
| Config | PyYAML |
| Tests | pytest (14 tests) |
| Scheduling | GitHub Actions cron |
| Deployment | Docker, Azure App Service |
| Dataset | LogHub Hadoop (Zenodo CC BY 4.0) |

---

## Tests

```bash
pytest tests/ -v
```

14 tests covering: config loading, Hadoop log parsing, DataFrame conversion, severity counts, spike detection, email building, API endpoints, plot serving, and path traversal blocking.

`test_hadoop_loader` hits the real `sample_data/` directory and skips gracefully if it is not present. All other tests build entries in memory — no file I/O, no external dependencies.
