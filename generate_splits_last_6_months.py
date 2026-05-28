import math
import os
from datetime import datetime, timezone

import gpxpy
import pandas as pd


BASE_DIR = os.environ.get(
    "STRAVA_EXPORT_DIR", "/Users/toni/strav/export_56684747-2"
)
ACTIVITIES_CSV = os.path.join(BASE_DIR, "activities.csv")
ACTIVITIES_DIR = os.path.join(BASE_DIR, "activities")
OUTPUT_XLSX = "/Users/toni/strav/splits_last_6_months.xlsx"
OUTPUT_CSV = "/Users/toni/strav/splits_last_6_months.csv"
WORKOUT_COLUMNS = [
    "Activity ID",
    "Activity Date",
    "Activity Name",
    "Activity Type",
    "Activity Description",
    "Filename",
    "Elapsed Time",
    "Moving Time",
    "Distance",
    "Average Speed",
    "Max Speed",
    "Average Heart Rate",
    "Max Heart Rate",
    "Average Cadence",
    "Average Watts",
    "Calories",
    "Elevation Gain",
    "Start Time",
    "Gear",
]


def subtract_months(dt, months):
    year = dt.year
    month = dt.month - months
    while month <= 0:
        month += 12
        year -= 1

    if month == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=dt.tzinfo)
    else:
        next_month = datetime(year, month + 1, 1, tzinfo=dt.tzinfo)

    last_day = (next_month - pd.Timedelta(days=1)).day
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def normalize_timestamp(ts):
    if ts is None:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def extract_heart_rate(point):
    for extension in getattr(point, "extensions", []) or []:
        for child in list(extension):
            tag_name = child.tag.rsplit("}", 1)[-1].lower()
            if tag_name == "hr" and child.text is not None:
                try:
                    return float(child.text)
                except ValueError:
                    return None
    return None


def haversine_meters(lat1, lon1, lat2, lon2):
    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def read_gpx_points(gpx_path):
    with open(gpx_path, "r", encoding="utf-8") as handle:
        gpx = gpxpy.parse(handle)

    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                timestamp = normalize_timestamp(point.time)
                if (
                    point.latitude is None
                    or point.longitude is None
                    or timestamp is None
                ):
                    continue
                points.append(
                    {
                        "latitude": point.latitude,
                        "longitude": point.longitude,
                        "timestamp": timestamp,
                        "heart_rate": extract_heart_rate(point),
                    }
                )
    return points


def compute_splits(points):
    if len(points) < 2:
        return [], 0.0, 0.0

    splits = []
    cumulative_distance = 0.0
    total_distance = 0.0
    split_start_time = points[0]["timestamp"]
    last_time = points[0]["timestamp"]
    next_split_mark = 1000.0
    current_split_hr = []
    if points[0]["heart_rate"] is not None:
        current_split_hr.append(points[0]["heart_rate"])

    for previous, current in zip(points, points[1:]):
        prev_time = previous["timestamp"]
        curr_time = current["timestamp"]
        prev_hr = previous["heart_rate"]
        curr_hr = current["heart_rate"]
        if prev_time is None or curr_time is None or curr_time <= prev_time:
            continue

        segment_distance = haversine_meters(
            previous["latitude"],
            previous["longitude"],
            current["latitude"],
            current["longitude"],
        )
        if segment_distance <= 0:
            last_time = curr_time
            continue

        segment_start_distance = cumulative_distance
        segment_end_distance = cumulative_distance + segment_distance
        segment_duration_sec = (curr_time - prev_time).total_seconds()

        while segment_end_distance >= next_split_mark:
            meters_into_segment = next_split_mark - segment_start_distance
            fraction = meters_into_segment / segment_distance
            split_timestamp = prev_time + pd.to_timedelta(
                segment_duration_sec * fraction, unit="s"
            )
            boundary_hr = None
            if prev_hr is not None and curr_hr is not None:
                boundary_hr = prev_hr + (curr_hr - prev_hr) * fraction
                current_split_hr.append(boundary_hr)
            split_time_sec = (split_timestamp - split_start_time).total_seconds()
            km_number = int(next_split_mark / 1000)
            splits.append(
                {
                    "km": km_number,
                    "split_time_sec": split_time_sec,
                    "pace_min_per_km": split_time_sec / 60.0,
                    "avg_hr_split": (
                        sum(current_split_hr) / len(current_split_hr)
                        if current_split_hr
                        else None
                    ),
                    "max_hr_split": max(current_split_hr) if current_split_hr else None,
                }
            )
            split_start_time = split_timestamp
            next_split_mark += 1000.0
            current_split_hr = [boundary_hr] if boundary_hr is not None else []

        if curr_hr is not None:
            current_split_hr.append(curr_hr)
        cumulative_distance = segment_end_distance
        total_distance = cumulative_distance
        last_time = curr_time

    total_time_sec = (last_time - points[0]["timestamp"]).total_seconds()
    return splits, total_distance, total_time_sec


def build_summary_dataframe(splits_df, metrics_df):
    if metrics_df.empty:
        return pd.DataFrame(
            columns=[
                "activity_file",
                "activity_date",
                "total_distance_km",
                "total_time_sec",
                "avg_pace",
                *WORKOUT_COLUMNS,
            ]
        )

    summary_df = metrics_df.copy()
    summary_df["total_distance_km"] = summary_df["total_distance_m"] / 1000.0
    summary_df["avg_pace"] = summary_df.apply(
        lambda row: (row["total_time_sec"] / 60.0) / row["total_distance_km"]
        if row["total_distance_km"] > 0
        else None,
        axis=1,
    )
    ordered_columns = [
        "activity_file",
        "activity_date",
        "total_distance_km",
        "total_time_sec",
        "avg_pace",
        *[column for column in WORKOUT_COLUMNS if column in summary_df.columns],
    ]
    return summary_df[ordered_columns].sort_values(["activity_date", "activity_file"])


def prepare_for_export(df):
    export_df = df.copy()
    if "activity_date" in export_df.columns and not export_df.empty:
        export_df["activity_date"] = pd.to_datetime(
            export_df["activity_date"], utc=True
        ).dt.tz_localize(None)
    return export_df


def main():
    now_utc = datetime.now(timezone.utc)
    cutoff = subtract_months(now_utc, 6)

    activities_df = pd.read_csv(ACTIVITIES_CSV)
    if "Filename" not in activities_df.columns:
        raise ValueError("activities.csv does not include a 'Filename' column.")

    activities_df["Activity ID"] = activities_df["Activity ID"].astype(str)
    candidate_rows = activities_df[
        activities_df["Filename"].fillna("").str.lower().str.endswith(".gpx")
    ].copy()
    selected_workout_columns = [
        column for column in WORKOUT_COLUMNS if column in candidate_rows.columns
    ]

    all_split_rows = []
    activity_metrics = []

    for _, activity in candidate_rows.iterrows():
        relative_filename = str(activity["Filename"]).strip()
        gpx_path = os.path.join(BASE_DIR, relative_filename)
        activity_file = os.path.basename(gpx_path)
        workout_data = {column: activity.get(column) for column in selected_workout_columns}

        print(f"Processing file {activity_file}...")

        if not os.path.exists(gpx_path):
            print(f"Skipping {activity_file}: file not found.")
            continue

        try:
            points = read_gpx_points(gpx_path)
        except Exception as exc:
            print(f"Skipping {activity_file}: could not parse GPX ({exc}).")
            continue

        if not points:
            print(f"Skipping {activity_file}: no valid points.")
            continue

        if len(points) < 2:
            print(f"Skipping {activity_file}: not enough timestamped points.")
            continue

        activity_date = points[0]["timestamp"]
        if activity_date < cutoff:
            print(f"Skipping {activity_file}: older than 6 months.")
            continue

        splits, total_distance_m, total_time_sec = compute_splits(points)

        activity_metrics.append(
            {
                "activity_file": activity_file,
                "activity_date": activity_date,
                "total_distance_m": total_distance_m,
                "total_time_sec": total_time_sec,
                **workout_data,
            }
        )

        for split in splits:
            all_split_rows.append(
                {
                    "activity_file": activity_file,
                    "activity_date": activity_date,
                    "km": split["km"],
                    "split_time_sec": split["split_time_sec"],
                    "pace_min_per_km": split["pace_min_per_km"],
                    "avg_hr_split": split["avg_hr_split"],
                    "max_hr_split": split["max_hr_split"],
                    **workout_data,
                }
            )

    splits_df = pd.DataFrame(
        all_split_rows,
        columns=[
            "activity_file",
            "activity_date",
            "km",
            "split_time_sec",
            "pace_min_per_km",
            "avg_hr_split",
            "max_hr_split",
            *selected_workout_columns,
        ],
    ).sort_values(["activity_date", "activity_file", "km"])

    metrics_df = pd.DataFrame(activity_metrics)
    summary_df = build_summary_dataframe(splits_df, metrics_df)

    export_splits_df = prepare_for_export(splits_df)
    export_summary_df = prepare_for_export(summary_df)

    export_splits_df.to_csv(OUTPUT_CSV, index=False)

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        export_splits_df.to_excel(writer, sheet_name="splits", index=False)
        export_summary_df.to_excel(writer, sheet_name="summary", index=False)

    print(f"Saved splits CSV to {OUTPUT_CSV}")
    print(f"Saved splits Excel to {OUTPUT_XLSX}")


if __name__ == "__main__":
    main()
