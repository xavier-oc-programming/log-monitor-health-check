import random
from datetime import datetime, timedelta
from pathlib import Path


LOG_MESSAGES = {
    'DEBUG': [
        "Cache hit for key '{key}'",
        "Query executed in {ms}ms — {rows} rows returned",
        "Session token refreshed for user {user_id}",
        "Config loaded from {path}",
    ],
    'INFO': [
        "Request completed: {method} {endpoint} — {status} in {ms}ms",
        "Pipeline stage '{stage}' completed — {rows} rows processed",
        "Model loaded: {model_name} ({size}MB)",
        "Scheduled job '{job}' started",
        "Scheduled job '{job}' completed in {duration}s",
        "User {user_id} authenticated successfully",
        "File exported: {filename} ({size}KB)",
        "Database connection established",
        "API rate limit: {remaining} requests remaining",
    ],
    'WARNING': [
        "Response time elevated: {endpoint} took {ms}ms (threshold: 500ms)",
        "Memory usage at {pct}% — approaching limit",
        "Retry attempt {n}/3 for {service}",
        "Deprecated function '{func}' called — migrate to '{new_func}'",
        "Cache miss rate elevated: {pct}% in last 60s",
        "Disk usage at {pct}% on {volume}",
    ],
    'ERROR': [
        "Database connection failed: {error}",
        "Request failed: {method} {endpoint} — {status} {reason}",
        "Pipeline stage '{stage}' failed: {error}",
        "File not found: {path}",
        "Authentication failed for user {user_id}: invalid credentials",
        "Timeout after {ms}ms connecting to {service}",
        "JSON decode error in response from {service}: {error}",
    ],
    'CRITICAL': [
        "Database connection pool exhausted — all {n} connections in use",
        "Out of memory: {service} killed by OOM killer",
        "Data corruption detected in {table}: checksum mismatch",
        "Service {service} unresponsive for {minutes} minutes",
        "Security alert: {n} failed login attempts from {ip}",
    ],
}


class LogGenerator:
    # Holds generation config as instance state so _choose_severity()
    # and _fill_template() share the same rng and spike settings without
    # needing long argument lists on every call.

    def __init__(self, config: dict, output_path: Path = Path('logs/app.log')):
        self.cfg         = config['log_generation']
        self.spike_cfg   = config['analysis']
        self.output_path = output_path
        # A seeded Random instance rather than random.seed() globally —
        # means multiple generators with different seeds can coexist
        # without interfering, which matters in tests.
        self.rng = random.Random(self.cfg['seed'])

    def generate(self) -> Path:
        """
        Generate log entries and write to self.output_path.

        Timestamps span the past 24 hours in ascending order with random
        gaps — not evenly spaced, simulating real activity bursts.

        Returns self.output_path.
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        n = self.cfg['n_entries']
        now = datetime.now()
        start = now - timedelta(hours=24)

        total_seconds = 24 * 3600
        gaps = [self.rng.expovariate(n / total_seconds) for _ in range(n)]
        total_gap = sum(gaps)
        scale = total_seconds / total_gap if total_gap > 0 else 1.0
        gaps = [g * scale for g in gaps]

        timestamps = []
        t = start
        for gap in gaps:
            t += timedelta(seconds=gap)
            timestamps.append(t)

        loggers = ['app.service', 'app.db', 'app.api', 'app.scheduler', 'app.auth']

        with open(self.output_path, 'w') as f:
            for i, ts in enumerate(timestamps):
                level = self._choose_severity(i)
                template = self.rng.choice(LOG_MESSAGES[level])
                message = self._fill_template(template)
                logger = self.rng.choice(loggers)
                line = f"{ts.strftime('%Y-%m-%dT%H:%M:%S')} — {level} — {logger} — {message}\n"
                f.write(line)

        return self.output_path

    def _choose_severity(self, entry_index: int) -> str:
        """
        Choose a severity level for this entry.

        Outside the spike window: sample from severity_weights.
        Inside the spike window: raise ERROR probability to
        spike_error_prob and redistribute remaining weight proportionally.
        """
        # The spike between spike_start_entry and spike_end_entry is
        # intentional — real monitoring tools must distinguish genuine
        # anomalies from statistical noise. A sharp localised ERROR spike
        # mirrors what happens during deployments, traffic surges, and
        # infrastructure failures.
        spike_start = self.spike_cfg['spike_start_entry']
        spike_end   = self.spike_cfg['spike_end_entry']
        spike_prob  = self.spike_cfg['spike_error_prob']

        weights = dict(self.cfg['severity_weights'])

        if spike_start <= entry_index < spike_end:
            non_error_total = sum(v for k, v in weights.items() if k != 'ERROR')
            remaining = 1.0 - spike_prob
            for k in weights:
                if k != 'ERROR':
                    weights[k] = (weights[k] / non_error_total) * remaining
            weights['ERROR'] = spike_prob

        levels = list(weights.keys())
        probs  = list(weights.values())
        return self.rng.choices(levels, weights=probs, k=1)[0]

    def _fill_template(self, template: str) -> str:
        """
        Fill a message template with realistic random values.
        """
        func = self.rng.choice(['get_user', 'process_order', 'send_email'])
        replacements = {
            'method':     self.rng.choice(['GET', 'POST', 'PUT', 'DELETE']),
            'endpoint':   self.rng.choice(['/api/predict', '/api/score', '/health', '/api/data', '/api/users', '/api/export']),
            'status':     str(self.rng.choice([200, 201, 400, 401, 404, 500, 503])),
            'ms':         str(self.rng.randint(10, 2000)),
            'rows':       str(self.rng.randint(1, 50000)),
            'pct':        str(self.rng.randint(60, 98)),
            'n':          str(self.rng.randint(1, 100)),
            'user_id':    f"user_{self.rng.randint(1000, 9999)}",
            'service':    self.rng.choice(['db', 'cache', 'auth', 'payment-api']),
            'error':      self.rng.choice(['timeout', 'connection refused', 'SSL error']),
            'ip':         f"{self.rng.randint(1,254)}.{self.rng.randint(1,254)}.x.x",
            'stage':      self.rng.choice(['ingest', 'transform', 'validate', 'export']),
            'job':        self.rng.choice(['daily-report', 'data-sync', 'cleanup']),
            'model_name': self.rng.choice(['classifier-v2', 'recommender-v1', 'scorer-v3']),
            'table':      self.rng.choice(['orders', 'users', 'payments', 'events']),
            'volume':     self.rng.choice(['/var/data', '/tmp', '/var/log']),
            'key':        f"cache:{self.rng.choice(['user','session','config'])}:{self.rng.randint(1,999)}",
            'path':       f"/var/data/{self.rng.choice(['input','output','temp'])}.csv",
            'func':       func,
            'new_func':   f"{func}_v2",
            'filename':   f"export_{self.rng.randint(1000,9999)}.csv",
            'minutes':    str(self.rng.randint(1, 30)),
            'remaining':  str(self.rng.randint(0, 1000)),
            'size':       str(self.rng.randint(1, 500)),
            'duration':   str(self.rng.randint(1, 300)),
            'reason':     self.rng.choice(['Not Found', 'Unauthorized', 'Bad Gateway']),
        }
        result = template
        for key, value in replacements.items():
            result = result.replace('{' + key + '}', value)
        return result
