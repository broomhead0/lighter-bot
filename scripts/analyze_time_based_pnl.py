#!/usr/bin/env python3
"""
Time-Based PnL Analysis

Analyze PnL trends by:
- Day of week (Monday-Sunday)
- Hour of day (0-23)
- Market hours (NY 9am-4pm ET vs overnight vs weekend)
- Time periods (Morning 6am-12pm, Afternoon 12pm-6pm, Evening 6pm-12am, Night 12am-6am)

Purpose: Identify optimal trading windows and potentially pause/scale during unprofitable periods.
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pytz


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze time-based PnL patterns")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/analysis/pnl_5m_recent.csv"),
        help="Path to PnL CSV file (default: data/analysis/pnl_5m_recent.csv).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/analysis/time_based_pnl_analysis.csv"),
        help="Path to output CSV file (default: data/analysis/time_based_pnl_analysis.csv).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("docs/analysis/time_based_pnl_report.md"),
        help="Path to output report markdown file (default: docs/analysis/time_based_pnl_report.md).",
    )
    return parser.parse_args()


def parse_timestamp(ts: str | int) -> datetime:
    """Parse timestamp (milliseconds or seconds) to datetime."""
    ts_int = int(float(ts))
    # Handle milliseconds vs seconds
    if ts_int > 1e10:  # milliseconds
        ts_int = ts_int // 1000
    return datetime.fromtimestamp(ts_int, tz=pytz.UTC)


def categorize_hour(hour: int, tz: pytz.BaseTzInfo = pytz.UTC) -> str:
    """Categorize hour into time periods."""
    # Convert to ET for market hours analysis
    et_hour = (hour - 5) % 24 if tz == pytz.UTC else hour
    if 6 <= et_hour < 12:
        return "Morning (6am-12pm ET)"
    elif 12 <= et_hour < 18:
        return "Afternoon (12pm-6pm ET)"
    elif 18 <= et_hour < 24:
        return "Evening (6pm-12am ET)"
    else:
        return "Night (12am-6am ET)"


def is_ny_market_hours(dt: datetime) -> bool:
    """Check if datetime is during NY market hours (9am-4pm ET)."""
    et = dt.astimezone(pytz.timezone("America/New_York"))
    return 9 <= et.hour < 16 and et.weekday() < 5  # Monday-Friday


def is_weekend(dt: datetime) -> bool:
    """Check if datetime is weekend."""
    return dt.weekday() >= 5  # Saturday = 5, Sunday = 6


def analyze_time_based_pnl(input_path: Path) -> Dict[str, any]:
    """Analyze PnL by time periods."""
    stats = {
        "by_day_of_week": defaultdict(lambda: {"pnl": 0.0, "count": 0, "volume": 0.0}),
        "by_hour": defaultdict(lambda: {"pnl": 0.0, "count": 0, "volume": 0.0}),
        "by_time_period": defaultdict(lambda: {"pnl": 0.0, "count": 0, "volume": 0.0}),
        "by_market_hours": defaultdict(lambda: {"pnl": 0.0, "count": 0, "volume": 0.0}),
        "total": {"pnl": 0.0, "count": 0, "volume": 0.0},
    }

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    with input_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # Parse timestamp
                ts = int(row.get("bucket_start_ts", row.get("start_ts", 0)))
                dt = parse_timestamp(ts)

                # Get PnL and volume
                pnl = float(row.get("realized_quote", 0.0))
                volume = float(row.get("notional_abs", 0.0))
                fill_count = int(row.get("fill_count", 0))

                # Update totals
                stats["total"]["pnl"] += pnl
                stats["total"]["count"] += fill_count
                stats["total"]["volume"] += volume

                # By day of week
                day_name = day_names[dt.weekday()]
                stats["by_day_of_week"][day_name]["pnl"] += pnl
                stats["by_day_of_week"][day_name]["count"] += fill_count
                stats["by_day_of_week"][day_name]["volume"] += volume

                # By hour (ET timezone)
                et = dt.astimezone(pytz.timezone("America/New_York"))
                hour_et = et.hour
                stats["by_hour"][hour_et]["pnl"] += pnl
                stats["by_hour"][hour_et]["count"] += fill_count
                stats["by_hour"][hour_et]["volume"] += volume

                # By time period
                time_period = categorize_hour(et.hour, et.tzinfo)
                stats["by_time_period"][time_period]["pnl"] += pnl
                stats["by_time_period"][time_period]["count"] += fill_count
                stats["by_time_period"][time_period]["volume"] += volume

                # By market hours
                if is_weekend(dt):
                    market_category = "Weekend"
                elif is_ny_market_hours(dt):
                    market_category = "NY Market Hours (9am-4pm ET)"
                else:
                    market_category = "Overnight (Outside NY Hours)"
                stats["by_market_hours"][market_category]["pnl"] += pnl
                stats["by_market_hours"][market_category]["count"] += fill_count
                stats["by_market_hours"][market_category]["volume"] += volume

            except (ValueError, KeyError) as e:
                print(f"Warning: Skipping row due to error: {e}")
                continue

    return stats


def calculate_metrics(stats: Dict) -> Dict:
    """Calculate per-fill and per-volume metrics."""
    metrics = {}
    for category, data in stats.items():
        if category == "total":
            continue
        metrics[category] = {}
        for key, values in data.items():
            pnl = values["pnl"]
            count = values["count"]
            volume = values["volume"]
            metrics[category][key] = {
                **values,
                "pnl_per_fill": pnl / count if count > 0 else 0.0,
                "pnl_per_volume": pnl / volume if volume > 0 else 0.0,
            }
    return metrics


def write_csv(output_path: Path, stats: Dict, metrics: Dict) -> None:
    """Write analysis to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    # By day of week
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
        if day in stats["by_day_of_week"]:
            row = stats["by_day_of_week"][day]
            row_metrics = metrics["by_day_of_week"][day]
            rows.append({
                "category": "day_of_week",
                "period": day,
                "pnl": row["pnl"],
                "fill_count": row["count"],
                "volume": row["volume"],
                "pnl_per_fill": row_metrics["pnl_per_fill"],
                "pnl_per_volume": row_metrics["pnl_per_volume"],
            })

    # By hour
    for hour in range(24):
        if hour in stats["by_hour"]:
            row = stats["by_hour"][hour]
            row_metrics = metrics["by_hour"][hour]
            rows.append({
                "category": "hour_of_day",
                "period": f"{hour:02d}:00 ET",
                "pnl": row["pnl"],
                "fill_count": row["count"],
                "volume": row["volume"],
                "pnl_per_fill": row_metrics["pnl_per_fill"],
                "pnl_per_volume": row_metrics["pnl_per_volume"],
            })

    # By time period
    for period in ["Morning (6am-12pm ET)", "Afternoon (12pm-6pm ET)", "Evening (6pm-12am ET)", "Night (12am-6am ET)"]:
        if period in stats["by_time_period"]:
            row = stats["by_time_period"][period]
            row_metrics = metrics["by_time_period"][period]
            rows.append({
                "category": "time_period",
                "period": period,
                "pnl": row["pnl"],
                "fill_count": row["count"],
                "volume": row["volume"],
                "pnl_per_fill": row_metrics["pnl_per_fill"],
                "pnl_per_volume": row_metrics["pnl_per_volume"],
            })

    # By market hours
    for market_cat in ["NY Market Hours (9am-4pm ET)", "Overnight (Outside NY Hours)", "Weekend"]:
        if market_cat in stats["by_market_hours"]:
            row = stats["by_market_hours"][market_cat]
            row_metrics = metrics["by_market_hours"][market_cat]
            rows.append({
                "category": "market_hours",
                "period": market_cat,
                "pnl": row["pnl"],
                "fill_count": row["count"],
                "volume": row["volume"],
                "pnl_per_fill": row_metrics["pnl_per_fill"],
                "pnl_per_volume": row_metrics["pnl_per_volume"],
            })

    with output_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["category", "period", "pnl", "fill_count", "volume", "pnl_per_fill", "pnl_per_volume"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {output_path}")


def write_report(report_path: Path, stats: Dict, metrics: Dict) -> None:
    """Write markdown report."""
    report_path.parent.mkdir(parents=True, exist_ok=True)

    total = stats["total"]
    total_pnl = total["pnl"]
    total_count = total["count"]
    total_volume = total["volume"]

    lines = [
        "# Time-Based PnL Analysis Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total PnL**: ${total_pnl:.2f}",
        f"- **Total Fills**: {total_count:,}",
        f"- **Total Volume**: ${total_volume:,.2f}",
        f"- **Average PnL per Fill**: ${total_pnl / total_count:.4f}" if total_count > 0 else "- **Average PnL per Fill**: N/A",
        "",
        "---",
        "",
        "## 📅 By Day of Week",
        "",
        "| Day | PnL | Fills | Volume | PnL/Fill | PnL/Volume |",
        "|-----|-----|-------|--------|----------|------------|",
    ]

    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    for day in day_order:
        if day in stats["by_day_of_week"]:
            row = stats["by_day_of_week"][day]
            row_metrics = metrics["by_day_of_week"][day]
            lines.append(
                f"| {day} | ${row['pnl']:.2f} | {row['count']:,} | ${row['volume']:,.2f} | "
                f"${row_metrics['pnl_per_fill']:.4f} | ${row_metrics['pnl_per_volume']:.6f} |"
            )

    lines.extend([
        "",
        "### Insights",
        "",
    ])
    # Find best/worst day
    best_day = max(
        stats["by_day_of_week"].items(),
        key=lambda x: x[1]["pnl"] / x[1]["count"] if x[1]["count"] > 0 else float("-inf"),
    )
    worst_day = min(
        stats["by_day_of_week"].items(),
        key=lambda x: x[1]["pnl"] / x[1]["count"] if x[1]["count"] > 0 else float("inf"),
    )
    lines.append(f"- **Best Day**: {best_day[0]} (${best_day[1]['pnl']/best_day[1]['count']:.4f} per fill)")
    lines.append(f"- **Worst Day**: {worst_day[0]} (${worst_day[1]['pnl']/worst_day[1]['count']:.4f} per fill)")

    lines.extend([
        "",
        "---",
        "",
        "## 🕐 By Hour of Day (ET)",
        "",
        "| Hour (ET) | PnL | Fills | Volume | PnL/Fill | PnL/Volume |",
        "|-----------|-----|-------|--------|----------|------------|",
    ])

    for hour in range(24):
        if hour in stats["by_hour"]:
            row = stats["by_hour"][hour]
            row_metrics = metrics["by_hour"][hour]
            lines.append(
                f"| {hour:02d}:00 | ${row['pnl']:.2f} | {row['count']:,} | ${row['volume']:,.2f} | "
                f"${row_metrics['pnl_per_fill']:.4f} | ${row_metrics['pnl_per_volume']:.6f} |"
            )

    lines.extend([
        "",
        "### Insights",
        "",
    ])
    # Find best/worst hours
    hours_with_data = [(h, stats["by_hour"][h]) for h in range(24) if h in stats["by_hour"] and stats["by_hour"][h]["count"] > 0]
    if hours_with_data:
        best_hour = max(hours_with_data, key=lambda x: x[1]["pnl"] / x[1]["count"])
        worst_hour = min(hours_with_data, key=lambda x: x[1]["pnl"] / x[1]["count"])
        lines.append(f"- **Best Hour**: {best_hour[0]:02d}:00 ET (${best_hour[1]['pnl']/best_hour[1]['count']:.4f} per fill)")
        lines.append(f"- **Worst Hour**: {worst_hour[0]:02d}:00 ET (${worst_hour[1]['pnl']/worst_hour[1]['count']:.4f} per fill)")

    lines.extend([
        "",
        "---",
        "",
        "## ⏰ By Time Period (ET)",
        "",
        "| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |",
        "|--------|-----|-------|--------|----------|------------|",
    ])

    period_order = ["Morning (6am-12pm ET)", "Afternoon (12pm-6pm ET)", "Evening (6pm-12am ET)", "Night (12am-6am ET)"]
    for period in period_order:
        if period in stats["by_time_period"]:
            row = stats["by_time_period"][period]
            row_metrics = metrics["by_time_period"][period]
            lines.append(
                f"| {period} | ${row['pnl']:.2f} | {row['count']:,} | ${row['volume']:,.2f} | "
                f"${row_metrics['pnl_per_fill']:.4f} | ${row_metrics['pnl_per_volume']:.6f} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 📈 By Market Hours",
        "",
        "| Period | PnL | Fills | Volume | PnL/Fill | PnL/Volume |",
        "|--------|-----|-------|--------|----------|------------|",
    ])

    market_order = ["NY Market Hours (9am-4pm ET)", "Overnight (Outside NY Hours)", "Weekend"]
    for market_cat in market_order:
        if market_cat in stats["by_market_hours"]:
            row = stats["by_market_hours"][market_cat]
            row_metrics = metrics["by_market_hours"][market_cat]
            lines.append(
                f"| {market_cat} | ${row['pnl']:.2f} | {row['count']:,} | ${row['volume']:,.2f} | "
                f"${row_metrics['pnl_per_fill']:.4f} | ${row_metrics['pnl_per_volume']:.6f} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## 💡 Recommendations",
        "",
        "Based on the analysis above:",
        "",
        "1. **Identify profitable hours** - Consider increasing activity during best hours",
        "2. **Identify losing hours** - Consider pausing or reducing size during worst hours",
        "3. **Day-of-week patterns** - Adjust strategy based on day-specific performance",
        "4. **Market hours** - Compare NY hours vs overnight vs weekend performance",
        "",
        "**Note**: This analysis uses `realized_quote` which is cash flow, not true FIFO realized PnL.",
        "For true PnL, monitor UI PnL or telemetry's `maker_fifo_realized_quote`.",
        "",
    ])

    with report_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote report to {report_path}")


def main() -> None:
    args = parse_args()

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        return

    print(f"Analyzing time-based PnL from {args.input}...")
    stats = analyze_time_based_pnl(args.input)
    metrics = calculate_metrics(stats)

    print(f"\nTotal PnL: ${stats['total']['pnl']:.2f}")
    print(f"Total Fills: {stats['total']['count']:,}")
    print(f"Total Volume: ${stats['total']['volume']:,.2f}")

    write_csv(args.output, stats, metrics)
    write_report(args.report, stats, metrics)

    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()

