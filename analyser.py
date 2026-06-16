from datetime import datetime

import pandas as pd


class LogReport:
    # A plain class rather than a dict so the report has typed fields,
    # a clear contract between analyser and email builder, and a
    # readable __repr__ for debugging — without the magic of @dataclass.

    def __init__(
        self,
        status: str,
        status_reason: str,
        total_entries: int,
        time_range: dict,
        severity_counts: dict,
        error_rate_pct: float,
        top_errors: list,
        anomaly_spikes: list,
        spike_count: int,
        recommendations: list,
        generated_at: str,
        hours_analysed: int
    ):
        self.status          = status
        self.status_reason   = status_reason
        self.total_entries   = total_entries
        self.time_range      = time_range
        self.severity_counts = severity_counts
        self.error_rate_pct  = error_rate_pct
        self.top_errors      = top_errors
        self.anomaly_spikes  = anomaly_spikes
        self.spike_count     = spike_count
        self.recommendations = recommendations
        self.generated_at    = generated_at
        self.hours_analysed  = hours_analysed

    def to_dict(self) -> dict:
        # FastAPI cannot serialise a class instance directly —
        # to_dict() converts to a plain dict that Pydantic can validate
        # against AnalysisResponse before returning as JSON.
        return self.__dict__

    def __repr__(self) -> str:
        return (
            f"LogReport(status={self.status!r}, "
            f"total_entries={self.total_entries}, "
            f"spike_count={self.spike_count}, "
            f"error_rate_pct={self.error_rate_pct:.1f}%)"
        )


def count_by_severity(df: pd.DataFrame) -> dict:
    """
    Count log entries by severity level.

    Returns:
      {
        "DEBUG": int, "INFO": int, "WARNING": int,
        "ERROR": int, "CRITICAL": int,
        "total": int,
        "error_rate": float,
        "warning_rate": float
      }
    """
    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    counts = {level: int((df['level'] == level).sum()) for level in levels}
    total = len(df)
    counts['total'] = total
    error_count = counts['ERROR'] + counts['CRITICAL']
    counts['error_rate'] = error_count / total if total > 0 else 0.0
    counts['warning_rate'] = counts['WARNING'] / total if total > 0 else 0.0
    return counts


def top_errors(df: pd.DataFrame, n: int = 10) -> list[dict]:
    """
    Find the n most frequent ERROR and CRITICAL messages by prefix.

    Groups by the first 60 characters of each message.

    # Grouping by prefix rather than exact message is necessary because
    # variable substitution makes each occurrence look unique — "Database
    # connection failed: timeout" and "Database connection failed: SSL
    # error" are the same underlying problem. Prefix truncation collapses
    # them. Production tools like Datadog use ML clustering for the same
    # reason; 60 characters is the lightweight equivalent.

    Returns:
      [{"message_prefix": str, "count": int, "pct_of_errors": float}]
    """
    error_df = df[df['level'].isin(['ERROR', 'CRITICAL'])].copy()
    if error_df.empty:
        return []

    error_df['prefix'] = error_df['message'].str[:60]
    grouped = error_df.groupby('prefix').size().nlargest(n).reset_index(name='count')

    total_errors = len(error_df)
    return [
        {
            'message_prefix': row['prefix'],
            'count': int(row['count']),
            'pct_of_errors': row['count'] / total_errors,
        }
        for _, row in grouped.iterrows()
    ]


def detect_spikes(df: pd.DataFrame, config: dict) -> list[dict]:
    """
    Detect time windows where error rate exceeds error_rate_threshold.

    Resamples into spike_window_minutes buckets using minute_window.
    For each bucket: error_rate = is_error.sum() / len(bucket).

    # Thresholding on rate rather than raw count makes this scale-invariant:
    # 5 errors out of 10 entries (50%) is far more alarming than 10 errors
    # out of 500 entries (2%), even though the raw count is higher.

    Returns:
      [{"window": str, "total_entries": int, "error_count": int,
        "error_rate": float,
        "severity": "warning" if error_rate < 0.25 else "critical"}]
    """
    if df.empty:
        return []

    threshold   = config['analysis']['error_rate_threshold']
    min_entries = config['analysis'].get('min_window_entries', 5)

    grouped = df.groupby('minute_window').agg(
        total_entries=('is_error', 'count'),
        error_count=('is_error', 'sum'),
    ).reset_index()

    grouped['error_rate'] = grouped['error_count'] / grouped['total_entries']
    # Require a minimum number of entries per window — single-entry windows
    # with one error produce 100% error rate but carry no statistical weight.
    spikes = grouped[
        (grouped['error_rate'] > threshold) &
        (grouped['total_entries'] >= min_entries)
    ].copy()

    result = []
    for _, row in spikes.iterrows():
        rate = float(row['error_rate'])
        result.append({
            'window':        str(row['minute_window']),
            'total_entries': int(row['total_entries']),
            'error_count':   int(row['error_count']),
            'error_rate':    rate,
            'severity':      'warning' if rate < 0.25 else 'critical',
        })

    return result


def hourly_breakdown(df: pd.DataFrame) -> list[dict]:
    """
    Count entries by hour of day, broken down by severity level.

    Returns:
      [{"hour": int, "DEBUG": int, "INFO": int, "WARNING": int,
        "ERROR": int, "CRITICAL": int, "total": int}]
    """
    if df.empty:
        return []

    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    pivoted = (
        df.groupby(['hour', 'level'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=levels, fill_value=0)
        .reset_index()
    )
    pivoted['total'] = pivoted[levels].sum(axis=1)

    return [
        {
            'hour':     int(row['hour']),
            'DEBUG':    int(row.get('DEBUG', 0)),
            'INFO':     int(row.get('INFO', 0)),
            'WARNING':  int(row.get('WARNING', 0)),
            'ERROR':    int(row.get('ERROR', 0)),
            'CRITICAL': int(row.get('CRITICAL', 0)),
            'total':    int(row['total']),
        }
        for _, row in pivoted.iterrows()
    ]


def generate_summary(
    df: pd.DataFrame,
    severity_counts: dict,
    top_errors_list: list[dict],
    spikes: list[dict],
    hours: int
) -> LogReport:
    """
    Combine all analysis results into a LogReport instance.

    Status logic:
      CRITICAL — any spike has severity="critical" OR error_rate >= 0.15
      WARNING  — any spikes present OR error_rate >= threshold
      HEALTHY  — otherwise

    Returns a LogReport instance.
    """
    error_rate     = severity_counts['error_rate']
    error_rate_pct = round(error_rate * 100, 2)
    threshold      = 0.25
    spike_count    = len(spikes)

    has_critical_spike = any(s['severity'] == 'critical' for s in spikes)

    if has_critical_spike or error_rate >= 0.15:
        status = 'CRITICAL'
        status_reason = (
            f"Critical anomaly spike detected" if has_critical_spike
            else f"Error rate {error_rate_pct}% exceeds critical threshold"
        )
    elif spike_count > 0 or error_rate >= threshold:
        status = 'WARNING'
        status_reason = (
            f"{spike_count} anomaly spike(s) detected" if spike_count > 0
            else f"Error rate {error_rate_pct}% above threshold"
        )
    else:
        status = 'HEALTHY'
        status_reason = 'Error rate within normal bounds'

    time_range = {}
    if not df.empty:
        time_range = {
            'start': df['timestamp'].min().strftime('%Y-%m-%d %H:%M'),
            'end':   df['timestamp'].max().strftime('%Y-%m-%d %H:%M'),
        }

    recommendations = []
    top_error_name = top_errors_list[0]['message_prefix'] if top_errors_list else 'N/A'

    if error_rate >= threshold:
        recommendations.append(
            f"Error rate is {error_rate_pct}% — above the {int(threshold*100)}% threshold. "
            f"Most frequent error: '{top_error_name}'."
        )

    top_spikes = sorted(spikes, key=lambda s: s['error_rate'], reverse=True)[:5]
    for spike in top_spikes:
        recommendations.append(
            f"Anomaly spike at {spike['window']}: {spike['error_count']} errors in 5 minutes "
            f"({spike['error_rate']:.0%} error rate). Investigate what changed at this time."
        )

    if top_errors_list:
        top = top_errors_list[0]
        recommendations.append(
            f"'{top['message_prefix']}' occurred {top['count']} times — consider adding retry logic."
        )

    return LogReport(
        status          = status,
        status_reason   = status_reason,
        total_entries   = severity_counts['total'],
        time_range      = time_range,
        severity_counts = severity_counts,
        error_rate_pct  = error_rate_pct,
        top_errors      = top_errors_list,
        anomaly_spikes  = spikes,
        spike_count     = spike_count,
        recommendations = recommendations,
        generated_at    = datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        hours_analysed  = hours,
    )
