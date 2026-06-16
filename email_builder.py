from datetime import datetime

from analyser import LogReport


SEVERITY_COLOURS = {
    'DEBUG':    '#94A3B8',
    'INFO':     '#22C55E',
    'WARNING':  '#F59E0B',
    'ERROR':    '#EF4444',
    'CRITICAL': '#7C3AED',
}

STATUS_COLOURS = {
    'HEALTHY':  {'bg': '#D1FAE5', 'text': '#065F46', 'border': '#6EE7B7'},
    'WARNING':  {'bg': '#FEF3C7', 'text': '#92400E', 'border': '#FCD34D'},
    'CRITICAL': {'bg': '#FEE2E2', 'text': '#7F1D1D', 'border': '#FCA5A5'},
}


def build_html_report(report: LogReport, config: dict) -> str:
    """
    Build a self-contained HTML email body from a LogReport.
    All CSS is inline — email clients strip <style> tags.
    Max width 700px, centred, white background, Arial font.
    Renders correctly in Gmail, Outlook, Apple Mail.
    """
    sc = STATUS_COLOURS[report.status]

    if report.status == 'HEALTHY':
        status_label = '&#10003; System Healthy &#8212; error rate within normal bounds'
    elif report.status == 'WARNING':
        status_label = f'&#9888; Warning &#8212; {report.status_reason}'
    else:
        status_label = f'&#10007; Critical &#8212; {report.status_reason}'

    time_start = report.time_range.get('start', 'N/A')
    time_end   = report.time_range.get('end', 'N/A')

    # ── Header ────────────────────────────────────────────────────────────
    header = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="background:#1E293B;">
      <tr>
        <td style="padding:32px 40px;">
          <h1 style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:24px;
                     color:#FFFFFF;font-weight:bold;">Log Health Report</h1>
          <p style="margin:8px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:13px;
                    color:#94A3B8;">
            Generated {report.generated_at} &middot; Last {report.hours_analysed} hours analysed
          </p>
        </td>
      </tr>
    </table>
    """

    # ── Status banner ─────────────────────────────────────────────────────
    banner = f"""
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{sc['bg']};border-left:4px solid {sc['border']};">
      <tr>
        <td style="padding:16px 40px;font-family:Arial,Helvetica,sans-serif;
                   font-size:15px;font-weight:bold;color:{sc['text']};">
          {status_label}
        </td>
      </tr>
    </table>
    """

    # ── Metric cards ──────────────────────────────────────────────────────
    def card(label, value):
        return f"""
        <td width="25%" style="padding:8px;">
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:6px;">
            <tr>
              <td style="padding:20px;text-align:center;font-family:Arial,Helvetica,sans-serif;">
                <div style="font-size:28px;font-weight:bold;color:#1E293B;">{value}</div>
                <div style="font-size:12px;color:#64748B;margin-top:4px;">{label}</div>
              </td>
            </tr>
          </table>
        </td>
        """

    spike_display = str(report.spike_count) if report.spike_count > 0 else '0'
    time_display  = f"{time_start[:10]}" if time_start != 'N/A' else 'N/A'

    metric_cards = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:0;">
      <tr>
        {card('Total Entries', f'{report.total_entries:,}')}
        {card('Error Rate', f'{report.error_rate_pct}%')}
        {card('Anomaly Spikes', spike_display)}
        {card('Date', time_display)}
      </tr>
    </table>
    """

    # ── Severity breakdown ────────────────────────────────────────────────
    severity_rows = ''
    total = report.severity_counts.get('total', 1) or 1
    for level in ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']:
        count = report.severity_counts.get(level, 0)
        pct   = round(count / total * 100, 1)
        colour = SEVERITY_COLOURS[level]
        severity_rows += f"""
        <tr style="border-left:4px solid {colour};">
          <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                     font-size:13px;font-weight:bold;color:{colour};
                     border-left:4px solid {colour};">{level}</td>
          <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                     font-size:13px;color:#374151;">{count:,}</td>
          <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                     font-size:13px;color:#6B7280;">{pct}%</td>
        </tr>
        """

    severity_table = f"""
    <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
               color:#1E293B;margin:24px 0 12px;">Severity Breakdown</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;background:#FFFFFF;
                  border:1px solid #E2E8F0;border-radius:6px;overflow:hidden;">
      <tr style="background:#F1F5F9;">
        <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                   font-size:12px;text-align:left;color:#374151;">Level</th>
        <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                   font-size:12px;text-align:left;color:#374151;">Count</th>
        <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                   font-size:12px;text-align:left;color:#374151;">% of total</th>
      </tr>
      {severity_rows}
    </table>
    """

    # ── Top errors ────────────────────────────────────────────────────────
    top_errors_section = ''
    if report.top_errors:
        error_rows = ''
        for i, err in enumerate(report.top_errors, 1):
            error_rows += f"""
            <tr style="{'background:#F8FAFC;' if i % 2 == 0 else ''}">
              <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                         font-size:13px;color:#6B7280;">{i}</td>
              <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                         font-size:13px;color:#374151;font-family:monospace;">{err['message_prefix']}</td>
              <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                         font-size:13px;color:#374151;">{err['count']:,}</td>
              <td style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                         font-size:13px;color:#6B7280;">{err['pct_of_errors']:.1%}</td>
            </tr>
            """

        top_errors_section = f"""
        <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
                   color:#1E293B;margin:24px 0 12px;">Top Errors</h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;background:#FFFFFF;
                      border:1px solid #E2E8F0;border-radius:6px;overflow:hidden;">
          <tr style="background:#F1F5F9;">
            <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                       font-size:12px;text-align:left;color:#374151;">#</th>
            <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                       font-size:12px;text-align:left;color:#374151;">Error message prefix</th>
            <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                       font-size:12px;text-align:left;color:#374151;">Count</th>
            <th style="padding:10px 16px;font-family:Arial,Helvetica,sans-serif;
                       font-size:12px;text-align:left;color:#374151;">% of errors</th>
          </tr>
          {error_rows}
        </table>
        """

    # ── Anomaly spikes ────────────────────────────────────────────────────
    if report.anomaly_spikes:
        spike_cards = ''
        for spike in report.anomaly_spikes:
            badge_bg = '#FEF3C7' if spike['severity'] == 'warning' else '#FEE2E2'
            badge_text = '#92400E' if spike['severity'] == 'warning' else '#7F1D1D'
            badge_label = spike['severity'].upper()
            spike_cards += f"""
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#FFFFFF;border:1px solid #E2E8F0;
                          border-radius:6px;margin-bottom:8px;">
              <tr>
                <td style="padding:16px;">
                  <span style="font-family:Arial,Helvetica,sans-serif;font-size:12px;
                               font-weight:bold;background:{badge_bg};color:{badge_text};
                               padding:2px 8px;border-radius:4px;">{badge_label}</span>
                  <span style="font-family:Arial,Helvetica,sans-serif;font-size:13px;
                               color:#374151;margin-left:12px;">{spike['window']}</span>
                  <span style="font-family:Arial,Helvetica,sans-serif;font-size:13px;
                               color:#6B7280;margin-left:16px;">
                    {spike['error_count']} errors / {spike['total_entries']} total
                    ({spike['error_rate']:.0%} error rate)
                  </span>
                </td>
              </tr>
            </table>
            """
        spikes_section = f"""
        <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
                   color:#1E293B;margin:24px 0 12px;">Anomaly Spikes</h2>
        {spike_cards}
        """
    else:
        spikes_section = f"""
        <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
                   color:#1E293B;margin:24px 0 12px;">Anomaly Spikes</h2>
        <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;
                  color:#6B7280;">No anomalies detected in this period.</p>
        """

    # ── Recommendations ───────────────────────────────────────────────────
    if report.recommendations:
        rec_items = ''.join(
            f'<li style="margin-bottom:8px;font-family:Arial,Helvetica,sans-serif;'
            f'font-size:13px;color:#92400E;">{r}</li>'
            for r in report.recommendations
        )
        recs_section = f"""
        <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
                   color:#1E293B;margin:24px 0 12px;">Recommendations</h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:6px;">
          <tr>
            <td style="padding:16px 24px;">
              <ol style="margin:0;padding-left:20px;">{rec_items}</ol>
            </td>
          </tr>
        </table>
        """
    else:
        recs_section = f"""
        <h2 style="font-family:Arial,Helvetica,sans-serif;font-size:16px;
                   color:#1E293B;margin:24px 0 12px;">Recommendations</h2>
        <p style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#6B7280;">
          No recommendations &#8212; system is operating normally.
        </p>
        """

    # ── Footer ────────────────────────────────────────────────────────────
    footer = """
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:#F8FAFC;border-top:1px solid #E2E8F0;margin-top:32px;">
      <tr>
        <td style="padding:20px 40px;text-align:center;font-family:Arial,Helvetica,sans-serif;
                   font-size:12px;color:#94A3B8;">
          Part 1 of 4 &#8212; Log Monitoring Series &middot;
          <a href="https://github.com/xavier-oc-programming/log-monitor-health-check"
             style="color:#64748B;">GitHub</a>
        </td>
      </tr>
    </table>
    """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Log Health Report</title>
</head>
<body style="margin:0;padding:0;background:#F1F5F9;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5F9;">
    <tr>
      <td align="center" style="padding:24px 0;">
        <table width="700" cellpadding="0" cellspacing="0"
               style="max-width:700px;width:100%;background:#FFFFFF;
                      border-radius:8px;overflow:hidden;
                      box-shadow:0 1px 3px rgba(0,0,0,0.1);">
          <tr><td>{header}</td></tr>
          <tr><td>{banner}</td></tr>
          <tr><td style="padding:24px 40px;">
            {metric_cards}
            {severity_table}
            {top_errors_section}
            {spikes_section}
            {recs_section}
          </td></tr>
          <tr><td>{footer}</td></tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    return html


def build_subject(report: LogReport, config: dict) -> str:
    """
    Build the email subject line.

    Format:
      "{prefix} — {status} — {date} — {spike_info}"
    """
    prefix = config['email'].get('subject_prefix', 'Log Health Report')
    date   = datetime.now().strftime('%Y-%m-%d')

    if report.status == 'HEALTHY':
        status_str = '✓ HEALTHY'
        spike_str  = ''
    elif report.status == 'WARNING':
        status_str = '⚠ WARNING'
        n = report.spike_count
        spike_str = f' — {n} anomaly {"spike" if n == 1 else "spikes"}' if n > 0 else ''
    else:
        status_str = '✗ CRITICAL'
        n = report.spike_count
        spike_str = f' — {n} anomaly {"spike" if n == 1 else "spikes"}' if n > 0 else ''

    return f"{prefix} — {status_str} — {date}{spike_str}"
