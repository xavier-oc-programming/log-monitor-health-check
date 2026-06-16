import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from analyser import count_by_severity, detect_spikes, generate_summary, hourly_breakdown, top_errors
from config_loader import load_config, validate_config
from log_generator import LogGenerator
from log_parser import parse_log_file, to_dataframe
from visualise import generate_all_plots

REPORT_CACHE: dict = {}
REPORT_LOADED: bool = False

_report_path = Path('reports/latest_report.json')
if _report_path.exists():
    REPORT_CACHE = json.loads(_report_path.read_text())
    REPORT_LOADED = True

ALLOWED_PLOTS = {
    'severity_distribution.png',
    'hourly_activity.png',
    'error_timeline.png',
    'top_errors.png',
}

app = FastAPI(
    title='Log Monitor API',
    description=(
        'Parses application logs, detects error patterns and anomaly spikes, '
        'and returns a plain-English health summary. '
        'POST /api/analyse regenerates a fresh log file and re-runs the full analysis.'
    ),
    version='1.0.0',
)


class AnalysisResponse(BaseModel):
    status: str
    status_reason: str
    total_entries: int
    time_range: dict
    severity_counts: dict
    error_rate_pct: float
    top_errors: list
    anomaly_spikes: list
    spike_count: int
    recommendations: list[str]
    generated_at: str
    hours_analysed: int


class HealthResponse(BaseModel):
    status: str
    report_loaded: bool
    log_file_exists: bool


@app.get('/', response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(Path('templates/index.html').read_text())


@app.get('/health', response_model=HealthResponse)
def health():
    return HealthResponse(
        status='ok',
        report_loaded=REPORT_LOADED,
        log_file_exists=Path('logs/app.log').exists(),
    )


@app.get('/api/report', response_model=AnalysisResponse)
def get_report():
    if not REPORT_LOADED:
        raise HTTPException(status_code=503, detail='No report available. POST /api/analyse first.')
    return REPORT_CACHE


@app.get('/api/severity-counts')
def get_severity_counts():
    if not REPORT_LOADED:
        raise HTTPException(status_code=503, detail='No report available. POST /api/analyse first.')
    return REPORT_CACHE['severity_counts']


@app.get('/api/top-errors')
def get_top_errors():
    if not REPORT_LOADED:
        raise HTTPException(status_code=503, detail='No report available. POST /api/analyse first.')
    return REPORT_CACHE['top_errors']


@app.get('/api/spikes')
def get_spikes():
    if not REPORT_LOADED:
        raise HTTPException(status_code=503, detail='No report available. POST /api/analyse first.')
    return REPORT_CACHE['anomaly_spikes']


@app.post('/api/analyse', response_model=AnalysisResponse)
def run_analysis():
    global REPORT_CACHE, REPORT_LOADED

    config = load_config(require_smtp=False)
    validate_config(config, require_smtp=False)

    Path('logs').mkdir(exist_ok=True)
    Path('reports').mkdir(exist_ok=True)
    Path('plots').mkdir(exist_ok=True)

    log_path  = LogGenerator(config).generate()
    hours     = config['analysis']['default_hours']
    entries   = parse_log_file(log_path, hours=hours)
    df        = to_dataframe(entries)
    severity  = count_by_severity(df)
    top_errs  = top_errors(df, n=config['analysis']['top_errors_n'])
    spikes    = detect_spikes(df, config)
    hourly    = hourly_breakdown(df)
    report    = generate_summary(df, severity, top_errs, spikes, hours=hours)
    threshold   = config['analysis']['error_rate_threshold']
    min_entries = config['analysis'].get('min_window_entries', 10)

    generate_all_plots(df, severity, hourly, spikes, top_errs,
                       threshold=threshold, min_entries=min_entries)

    report_dict = report.to_dict()
    Path('reports/latest_report.json').write_text(json.dumps(report_dict, default=str))

    REPORT_CACHE  = report_dict
    REPORT_LOADED = True

    return report_dict


@app.get('/plots/{filename}')
def serve_plot(filename: str):
    if filename not in ALLOWED_PLOTS:
        raise HTTPException(status_code=404, detail='Plot not found.')
    path = Path('plots') / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail='Plot not generated yet. POST /api/analyse first.')
    return FileResponse(path, media_type='image/png')
