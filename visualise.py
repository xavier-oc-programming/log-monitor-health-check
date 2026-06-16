from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd

PLOTS_DIR = Path('plots')

SEVERITY_COLOURS = {
    'DEBUG':    '#94A3B8',
    'INFO':     '#22C55E',
    'WARNING':  '#F59E0B',
    'ERROR':    '#EF4444',
    'CRITICAL': '#7C3AED',
}


def plot_severity_distribution(severity_counts: dict) -> str:
    """Horizontal bar chart of entry counts by severity, colour-coded."""
    PLOTS_DIR.mkdir(exist_ok=True)
    levels = ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    counts = [severity_counts.get(l, 0) for l in levels]
    colours = [SEVERITY_COLOURS[l] for l in levels]
    total = severity_counts.get('total', 1) or 1

    fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
    fig.patch.set_facecolor('#1E293B')
    ax.set_facecolor('#1E293B')

    bars = ax.barh(levels, counts, color=colours, height=0.6)
    for bar, count in zip(bars, counts):
        pct = count / total * 100
        ax.text(bar.get_width() + max(counts) * 0.01, bar.get_y() + bar.get_height() / 2,
                f'{count:,} ({pct:.1f}%)', va='center', color='#CBD5E1', fontsize=9)

    ax.set_xlabel('Count', color='#94A3B8', fontsize=10)
    ax.set_title('Severity Distribution', color='#F1F5F9', fontsize=12, fontweight='bold', pad=12)
    ax.tick_params(colors='#94A3B8')
    ax.spines[:].set_color('#334155')
    ax.set_xlim(0, max(counts) * 1.25)
    for spine in ax.spines.values():
        spine.set_color('#334155')

    plt.tight_layout()
    out = PLOTS_DIR / 'severity_distribution.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#1E293B')
    plt.close()
    return str(out)


def plot_hourly_activity(hourly_data: list[dict]) -> str:
    """Stacked bar chart of log volume by hour, stacked by severity."""
    PLOTS_DIR.mkdir(exist_ok=True)
    if not hourly_data:
        fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
        fig.patch.set_facecolor('#1E293B')
        out = PLOTS_DIR / 'hourly_activity.png'
        plt.savefig(out, dpi=150, facecolor='#1E293B')
        plt.close()
        return str(out)

    hours = [d['hour'] for d in hourly_data]
    levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    fig, ax = plt.subplots(figsize=(10, 4), dpi=150)
    fig.patch.set_facecolor('#1E293B')
    ax.set_facecolor('#1E293B')

    bottoms = [0] * len(hours)
    for level in levels:
        values = [d.get(level, 0) for d in hourly_data]
        ax.bar(hours, values, bottom=bottoms, color=SEVERITY_COLOURS[level],
               label=level, width=0.8)
        bottoms = [b + v for b, v in zip(bottoms, values)]

    ax.set_xlabel('Hour of day', color='#94A3B8', fontsize=10)
    ax.set_ylabel('Log entries', color='#94A3B8', fontsize=10)
    ax.set_title('Hourly Activity', color='#F1F5F9', fontsize=12, fontweight='bold', pad=12)
    ax.set_xticks(range(0, 24, 2))
    ax.tick_params(colors='#94A3B8')
    for spine in ax.spines.values():
        spine.set_color('#334155')
    patches = [mpatches.Patch(color=SEVERITY_COLOURS[l], label=l) for l in levels]
    ax.legend(handles=patches, loc='upper right', framealpha=0.3,
              labelcolor='#CBD5E1', facecolor='#1E293B', fontsize=8)

    plt.tight_layout()
    out = PLOTS_DIR / 'hourly_activity.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#1E293B')
    plt.close()
    return str(out)


def plot_error_timeline(df: pd.DataFrame, spikes: list[dict], threshold: float = 0.25,
                        min_entries: int = 10) -> str:
    """
    Bar chart of error rate per 5-minute window over 24 hours.
    Only windows with >= min_entries are plotted — sparse windows produce
    misleading 100% rates from single errors and obscure the real spike.
    Bars below threshold are grey; bars above are red.
    """
    PLOTS_DIR.mkdir(exist_ok=True)

    grouped = df.groupby('minute_window').agg(
        total=('is_error', 'count'),
        errors=('is_error', 'sum'),
    ).reset_index()
    grouped['error_rate'] = grouped['errors'] / grouped['total']

    # Drop sparse windows — they are statistically meaningless at this granularity
    grouped = grouped[grouped['total'] >= min_entries].reset_index(drop=True)

    if grouped.empty:
        fig, ax = plt.subplots(figsize=(12, 4), dpi=150)
        fig.patch.set_facecolor('#1E293B')
        ax.text(0.5, 0.5, 'Insufficient data', transform=ax.transAxes,
                ha='center', va='center', color='#64748B', fontsize=12)
        out = PLOTS_DIR / 'error_timeline.png'
        plt.savefig(out, dpi=150, facecolor='#1E293B')
        plt.close()
        return str(out)

    spike_windows = {s['window'] for s in spikes}
    colours = ['#EF4444' if r >= threshold else '#475569'
               for r in grouped['error_rate']]

    fig, ax = plt.subplots(figsize=(12, 4), dpi=150)
    fig.patch.set_facecolor('#1E293B')
    ax.set_facecolor('#1E293B')

    x = range(len(grouped))
    ax.bar(x, grouped['error_rate'], color=colours, width=0.8, alpha=0.9)

    # Only shade windows that have a bar — axvspan without a bar produces
    # a faint red ghost that implies a spike where no data is plotted.
    plotted_windows = set(grouped['minute_window'].astype(str))
    for i, (_, row) in enumerate(grouped.iterrows()):
        if str(row['minute_window']) in spike_windows and str(row['minute_window']) in plotted_windows:
            ax.axvspan(i - 0.5, i + 0.5, alpha=0.12, color='#EF4444', zorder=0)

    ax.axhline(threshold, color='#F59E0B', linestyle='--', linewidth=1.2,
               label=f'Threshold ({threshold:.0%})')

    tick_step = max(1, len(grouped) // 12)
    tick_positions = list(range(0, len(grouped), tick_step))
    tick_labels = [str(grouped.iloc[i]['minute_window'])[11:16] for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha='right', fontsize=7)

    ax.set_ylabel('Error rate', color='#94A3B8', fontsize=10)
    ax.set_title('Error Timeline — 5-min windows (populated only)', color='#F1F5F9',
                 fontsize=12, fontweight='bold', pad=12)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.0%}'))
    ax.tick_params(colors='#94A3B8')
    for spine in ax.spines.values():
        spine.set_color('#334155')

    above = mpatches.Patch(color='#EF4444', label='Above threshold')
    below = mpatches.Patch(color='#475569', label='Below threshold')
    thresh_line = plt.Line2D([0], [0], color='#F59E0B', linestyle='--',
                             linewidth=1.2, label=f'Threshold ({threshold:.0%})')
    ax.legend(handles=[above, below, thresh_line], framealpha=0.3,
              labelcolor='#CBD5E1', facecolor='#1E293B', fontsize=8)

    plt.tight_layout()
    out = PLOTS_DIR / 'error_timeline.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#1E293B')
    plt.close()
    return str(out)


def plot_top_errors(top_errors_list: list[dict]) -> str:
    """Horizontal bar chart of top error message prefixes."""
    PLOTS_DIR.mkdir(exist_ok=True)
    if not top_errors_list:
        fig, ax = plt.subplots(figsize=(8, 4), dpi=150)
        fig.patch.set_facecolor('#1E293B')
        ax.text(0.5, 0.5, 'No errors recorded', transform=ax.transAxes,
                ha='center', va='center', color='#94A3B8', fontsize=12)
        out = PLOTS_DIR / 'top_errors.png'
        plt.savefig(out, dpi=150, facecolor='#1E293B')
        plt.close()
        return str(out)

    labels = [e['message_prefix'][:45] + ('…' if len(e['message_prefix']) > 45 else '')
              for e in top_errors_list]
    counts = [e['count'] for e in top_errors_list]

    fig, ax = plt.subplots(figsize=(9, max(3, len(labels) * 0.45)), dpi=150)
    fig.patch.set_facecolor('#1E293B')
    ax.set_facecolor('#1E293B')

    bars = ax.barh(labels[::-1], counts[::-1], color='#EF4444', height=0.6)
    for bar, count in zip(bars, counts[::-1]):
        ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                str(count), va='center', color='#CBD5E1', fontsize=9)

    ax.set_xlabel('Occurrences', color='#94A3B8', fontsize=10)
    ax.set_title('Top Errors', color='#F1F5F9', fontsize=12, fontweight='bold', pad=12)
    ax.tick_params(colors='#94A3B8')
    ax.set_xlim(0, max(counts) * 1.2)
    for spine in ax.spines.values():
        spine.set_color('#334155')

    plt.tight_layout()
    out = PLOTS_DIR / 'top_errors.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='#1E293B')
    plt.close()
    return str(out)


def generate_all_plots(
    df: pd.DataFrame,
    severity_counts: dict,
    hourly_data: list[dict],
    spikes: list[dict],
    top_errors_list: list[dict],
    threshold: float = 0.25,
    min_entries: int = 10,
) -> list[str]:
    """Run all four plot functions. Return list of output paths."""
    return [
        plot_severity_distribution(severity_counts),
        plot_hourly_activity(hourly_data),
        plot_error_timeline(df, spikes, threshold=threshold, min_entries=min_entries),
        plot_top_errors(top_errors_list),
    ]
