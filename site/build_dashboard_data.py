from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from lxml import etree


ROOT = Path(__file__).resolve().parent.parent
SITE = Path(__file__).resolve().parent
EXPORT_XML = Path(
    os.environ.get(
        "APPLE_HEALTH_EXPORT_XML",
        str(ROOT / "MAY apple_health_export" / "export.xml"),
    )
)
ACTIVITIES_CSV = Path(
    os.environ.get(
        "STRAVA_ACTIVITIES_CSV",
        str(ROOT / "export_56684747-2" / "activities.csv"),
    )
)
SPLITS_CSV = ROOT / "splits_last_6_months.csv"
PLAN_CSV = ROOT / "run_plan_match_results.csv"
RUN_LOOKBACK_DAYS = 60
HEALTH_LOOKBACK_DAYS = 120
NUTRITION_LOOKBACK_DAYS = 21


def parse_xml_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")


def to_iso_date(value: str) -> str:
    return parse_xml_date(value).date().isoformat()


def pct(value: float) -> int:
    return int(round(value * 100))


def fmt(value: float | None, digits: int = 1) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def parse_activity_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(
        series, format="%b %d, %Y, %I:%M:%S %p", errors="coerce"
    )


def format_mmss(minutes: float | None) -> str | None:
    if minutes is None or pd.isna(minutes):
        return None
    total_seconds = int(round(float(minutes) * 60))
    mins, secs = divmod(total_seconds, 60)
    return f"{mins}:{secs:02d}"


def derive_5k_range(best_exact_min: float | None, best_split_min: float | None) -> str:
    candidates = [value for value in [best_exact_min, best_split_min] if value is not None]
    if not candidates:
        return "Unknown"
    best = min(candidates)
    lo = max(best, best - 0.3)
    hi = best + 0.3
    return f"{format_mmss(lo)}-{format_mmss(hi)}"


def safe_pct(numerator: int, denominator: int) -> int | None:
    if denominator <= 0:
        return None
    return int(round((numerator / denominator) * 100))


def ascii_bar(label: str, value: float, total: float, width: int = 22) -> str:
    total = total or 1
    filled = int(round((value / total) * width))
    return f"{label:<14} [{'#' * filled}{'.' * (width - filled)}] {value:g}"


def ascii_scale(title: str, value: float, lo: float, hi: float, width: int = 24) -> str:
    if hi <= lo:
        hi = lo + 1
    ratio = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    pos = min(width - 1, int(round(ratio * (width - 1))))
    line = ["-"] * width
    line[pos] = "|"
    return f"{title:<10} {lo:>5.1f} {''.join(line)} {hi:>5.1f}   now {value:.1f}"


def load_profile() -> dict:
    for _, elem in etree.iterparse(str(EXPORT_XML), events=("end",), tag="Me"):
        dob = elem.attrib.get("HKCharacteristicTypeIdentifierDateOfBirth")
        sex = elem.attrib.get("HKCharacteristicTypeIdentifierBiologicalSex", "")
        return {
            "name": "Toni",
            "dob": dob,
            "sex": sex.replace("HKBiologicalSex", ""),
            "age": 26,
            "height_cm": 183,
            "weight_range_kg": "90-93",
            "goals": [
                "Primary: sub-20 minute 5K",
                "Secondary: lose body fat while maintaining muscle",
            ],
            "constraints": [
                "light patella knee pain",
                "muscle retention matters",
                "Apple Watch not worn every day",
            ],
        }
    raise RuntimeError("Could not read Apple Health profile metadata.")


def load_runs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, str, str]:
    activities = pd.read_csv(ACTIVITIES_CSV)
    runs = activities[activities["Activity Type"].eq("Run")].copy()
    runs["dt"] = parse_activity_date_series(runs["Activity Date"])
    runs["date"] = runs["dt"].dt.date.astype(str)
    runs["distance_km"] = pd.to_numeric(runs["Distance"], errors="coerce")
    runs["moving_min"] = pd.to_numeric(runs["Moving Time"], errors="coerce") / 60
    runs["pace_min_km"] = runs["moving_min"] / runs["distance_km"]
    runs["avg_hr"] = pd.to_numeric(runs["Average Heart Rate"], errors="coerce")
    runs["max_hr"] = pd.to_numeric(runs["Max Heart Rate"], errors="coerce")
    runs["elev_m"] = pd.to_numeric(runs["Elevation Gain"], errors="coerce")
    runs["relative_effort"] = pd.to_numeric(runs["Relative Effort"], errors="coerce")

    splits = pd.read_csv(SPLITS_CSV)
    splits["activity_date"] = pd.to_datetime(splits["activity_date"])
    splits["date"] = splits["activity_date"].dt.date.astype(str)
    splits["pace_min_per_km"] = pd.to_numeric(splits["pace_min_per_km"], errors="coerce")
    splits["avg_hr_split"] = pd.to_numeric(splits["avg_hr_split"], errors="coerce")
    splits["Activity ID"] = pd.to_numeric(splits["Activity ID"], errors="coerce").astype("Int64")

    features = []
    for activity_id, group in splits.groupby("Activity ID"):
        group = group.sort_values("km").copy()
        pace = group["pace_min_per_km"]
        hr = group["avg_hr_split"]
        count = len(group)
        cv = pace.std() / pace.mean() if count > 1 and pace.mean() > 0 else None
        alternation = 0
        values = pace.to_numpy()
        for idx in range(1, len(values) - 1):
            if (values[idx] - values[idx - 1]) * (values[idx] - values[idx + 1]) > 0:
                alternation += 1
        half = max(1, count // 2)
        drift = None
        if hr.notna().sum() >= max(4, int(count * 0.6)):
            drift = hr.iloc[half:].mean() - hr.iloc[:half].mean()
        best5 = None
        if count >= 5:
            best5 = group["split_time_sec"].rolling(5).sum().min() / 60
        features.append(
            {
                "Activity ID": int(activity_id),
                "split_count": count,
                "split_pace_cv": cv,
                "alt_score": alternation,
                "hr_drift": drift,
                "best5_from_splits_min": best5,
                "split_fastest_pace": pace.min(),
                "split_slowest_pace": pace.max(),
            }
        )

    features_df = pd.DataFrame(features)
    runs = runs.merge(features_df, on="Activity ID", how="inner")

    classes = []
    for _, row in runs.iterrows():
        hr = row["avg_hr"]
        pace = row["pace_min_km"]
        dist = row["distance_km"]
        minutes = row["moving_min"]
        cv = row["split_pace_cv"]
        alt = row["alt_score"]

        label = "steady"
        if pd.notna(cv) and (
            (cv >= 0.11 and alt >= 2)
            or (row["split_fastest_pace"] <= 4.9 and row["split_slowest_pace"] - row["split_fastest_pace"] >= 1.0)
        ):
            label = "interval/repetition"
        elif dist >= 12 and minutes >= 70:
            label = "long"
        elif pd.notna(hr) and hr >= 170 and dist >= 4:
            label = "hard/5k effort"
        elif pd.notna(hr) and 158 <= hr < 170 and (pd.isna(cv) or cv < 0.09) and dist >= 5:
            label = "tempo/threshold"
        elif pd.notna(hr) and hr <= 150 and ((pace >= 5.7 and (pd.isna(cv) or cv < 0.08)) or minutes >= 30):
            label = "easy"
        elif dist < 3 and (pd.isna(hr) or hr < 150):
            label = "warmup/cooldown"
        elif dist < 4 and pd.notna(cv) and cv > 0.12:
            label = "strides/drills"
        classes.append(label)
    runs["actual_class"] = classes

    latest_run_dt = runs["dt"].max()
    if pd.isna(latest_run_dt):
        raise RuntimeError("Could not determine latest run date from Strava export.")
    plan_end = latest_run_dt.date().isoformat()
    plan_start = (latest_run_dt - pd.Timedelta(days=RUN_LOOKBACK_DAYS - 1)).date().isoformat()

    recent = runs[
        (runs["dt"] >= pd.Timestamp(plan_start))
        & (runs["dt"] <= pd.Timestamp(f"{plan_end} 23:59:59"))
    ].copy()
    recent["high_intensity"] = recent["actual_class"].isin(
        ["interval/repetition", "tempo/threshold", "hard/5k effort"]
    ) | (recent["avg_hr"] >= 158)
    recent["easy_like"] = recent["actual_class"].isin(["easy", "warmup/cooldown"]) | (recent["avg_hr"] <= 150)
    recent["week"] = recent["dt"].dt.to_period("W").astype(str)
    return runs, splits, recent, plan_start, plan_end


def load_health_daily(recovery_start: str, recovery_end: str) -> pd.DataFrame:
    metric_names = {
        "HKQuantityTypeIdentifierRestingHeartRate": "rhr",
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv",
        "HKQuantityTypeIdentifierStepCount": "steps",
        "HKQuantityTypeIdentifierActiveEnergyBurned": "active_kcal",
        "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_kcal",
        "HKQuantityTypeIdentifierBodyMass": "body_mass_kg",
        "HKQuantityTypeIdentifierBodyFatPercentage": "body_fat_pct",
        "HKQuantityTypeIdentifierVO2Max": "vo2max",
        "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_hr",
        "HKQuantityTypeIdentifierDietaryEnergyConsumed": "dietary_kcal",
        "HKQuantityTypeIdentifierDietaryProtein": "dietary_protein_g",
        "HKQuantityTypeIdentifierDietaryCarbohydrates": "dietary_carbs_g",
        "HKQuantityTypeIdentifierDietaryFatTotal": "dietary_fat_g",
        "HKQuantityTypeIdentifierDietarySugar": "dietary_sugar_g",
        "HKQuantityTypeIdentifierDietaryFiber": "dietary_fiber_g",
        "HKQuantityTypeIdentifierDietarySodium": "dietary_sodium_mg",
        "HKQuantityTypeIdentifierDietaryWater": "dietary_water_ml",
    }

    records: list[tuple[str, str, float]] = []
    source_records: list[tuple[str, str, str, float]] = []
    nutrition_source_records: list[tuple[str, str, str, str, str, float]] = []
    sleep: list[tuple[str, float]] = []
    summed_metrics = {
        "basal_kcal",
        "dietary_kcal",
        "dietary_protein_g",
        "dietary_carbs_g",
        "dietary_fat_g",
        "dietary_sugar_g",
        "dietary_fiber_g",
        "dietary_sodium_mg",
        "dietary_water_ml",
    }
    nutrition_metrics = summed_metrics - {"basal_kcal"}

    for _, elem in etree.iterparse(str(EXPORT_XML), events=("end",), tag="Record"):
        record_type = elem.get("type")
        start_date = elem.get("startDate")
        if not start_date:
            elem.clear()
            continue
        day = to_iso_date(start_date)
        if day < recovery_start or day > recovery_end:
            elem.clear()
            continue
        if record_type in metric_names:
            value = elem.get("value")
            if value is not None:
                metric_name = metric_names[record_type]
                numeric = float(value)
                records.append((day, metric_name, numeric))
                source_records.append((day, metric_name, elem.get("sourceName", "unknown"), numeric))
                if metric_name in nutrition_metrics:
                    nutrition_source_records.append(
                        (
                            day,
                            metric_name,
                            elem.get("sourceName", "unknown"),
                            start_date,
                            elem.get("endDate", ""),
                            numeric,
                        )
                    )
        elif record_type == "HKCategoryTypeIdentifierSleepAnalysis":
            end_date = elem.get("endDate")
            value = elem.get("value")
            if end_date and value and "Asleep" in value:
                start_dt = parse_xml_date(start_date)
                end_dt = parse_xml_date(end_date)
                sleep.append((day, (end_dt - start_dt).total_seconds() / 3600))
        elem.clear()

    daily_rows = []
    if records:
        frame = pd.DataFrame(records, columns=["date", "metric", "value"])
        source_frame = pd.DataFrame(source_records, columns=["date", "metric", "source", "value"])
        nutrition_frame = pd.DataFrame(
            nutrition_source_records,
            columns=["date", "metric", "source", "start_date", "end_date", "value"],
        )
        for (date, metric), group in frame.groupby(["date", "metric"]):
            values = group["value"]
            if metric == "basal_kcal":
                value = values.sum()
            elif metric in nutrition_metrics:
                unique_rows = (
                    nutrition_frame[
                        (nutrition_frame["date"] == date) & (nutrition_frame["metric"] == metric)
                    ]
                    .drop_duplicates(
                        subset=["source", "start_date", "end_date", "value"]
                    )
                )
                value = unique_rows["value"].sum()
            elif metric in {"steps", "active_kcal"}:
                per_source = (
                    source_frame[(source_frame["date"] == date) & (source_frame["metric"] == metric)]
                    .groupby("source", as_index=False)["value"]
                    .sum()
                )
                value = per_source["value"].max() if not per_source.empty else values.sum()
            elif metric in {"body_mass_kg", "body_fat_pct", "vo2max"}:
                value = values.iloc[-1]
            else:
                value = values.mean()
            daily_rows.append((date, metric, value))

    daily = pd.DataFrame(daily_rows, columns=["date", "metric", "value"])
    if not daily.empty:
        daily = daily.pivot(index="date", columns="metric", values="value").reset_index()
    else:
        daily = pd.DataFrame({"date": []})

    if sleep:
        sleep_df = pd.DataFrame(sleep, columns=["date", "sleep_hours"]).groupby("date", as_index=False)["sleep_hours"].sum()
        daily = daily.merge(sleep_df, on="date", how="outer")

    return daily.sort_values("date").reset_index(drop=True)


def series_tail(daily: pd.DataFrame, column: str, limit: int = 10, digits: int = 1) -> list[dict]:
    if column not in daily.columns:
        return []
    frame = daily[["date", column]].dropna().tail(limit)
    return [{"date": row["date"], "value": fmt(row[column], digits)} for _, row in frame.iterrows()]


def build_nutrition_focus(
    daily: pd.DataFrame,
    protein_min: int,
    fat_loss_floor: float,
    fat_loss_ceiling: float,
    recovery_end: str,
) -> dict:
    keys = [
        "dietary_kcal",
        "dietary_protein_g",
        "dietary_carbs_g",
        "dietary_fat_g",
        "dietary_fiber_g",
        "dietary_sugar_g",
        "dietary_sodium_mg",
        "dietary_water_ml",
    ]
    available = [key for key in keys if key in daily.columns]
    if not available:
        return {"days_logged": 0, "window_start": None, "window_end": recovery_end}

    window_start = (
        pd.Timestamp(recovery_end) - pd.Timedelta(days=NUTRITION_LOOKBACK_DAYS - 1)
    ).date().isoformat()
    frame = daily[["date", *available]].copy()
    frame = frame[(frame["date"] >= window_start) & (frame["date"] <= recovery_end)].sort_values("date")

    if frame.empty:
        return {"days_logged": 0, "window_start": window_start, "window_end": recovery_end}

    calorie_days = frame["dietary_kcal"].notna().sum() if "dietary_kcal" in frame.columns else 0
    protein_days = (
        frame["dietary_protein_g"].notna().sum() if "dietary_protein_g" in frame.columns else 0
    )
    protein_hit_days = (
        (frame["dietary_protein_g"] >= protein_min).sum()
        if "dietary_protein_g" in frame.columns
        else 0
    )
    kcal_in_range_days = (
        frame["dietary_kcal"].between(fat_loss_floor, fat_loss_ceiling).sum()
        if "dietary_kcal" in frame.columns
        else 0
    )

    averages = {}
    latest = {}
    for key, digits in [
        ("dietary_kcal", 0),
        ("dietary_protein_g", 0),
        ("dietary_carbs_g", 0),
        ("dietary_fat_g", 0),
        ("dietary_fiber_g", 0),
        ("dietary_sugar_g", 0),
        ("dietary_sodium_mg", 0),
        ("dietary_water_ml", 0),
    ]:
        if key not in frame.columns:
            continue
        values = frame[key].dropna()
        if values.empty:
            continue
        averages[key] = fmt(values.mean(), digits)
        latest[key] = fmt(values.iloc[-1], digits)

    if "dietary_water_ml" in averages:
        averages["dietary_water_l"] = fmt(averages["dietary_water_ml"] / 1000.0, 2)
    if "dietary_water_ml" in latest:
        latest["dietary_water_l"] = fmt(latest["dietary_water_ml"] / 1000.0, 2)

    recent_days = []
    preview = frame.tail(7)
    for _, row in preview.iterrows():
        recent_days.append(
            {
                "date": row["date"],
                "kcal": fmt(row.get("dietary_kcal"), 0),
                "protein_g": fmt(row.get("dietary_protein_g"), 0),
                "carbs_g": fmt(row.get("dietary_carbs_g"), 0),
                "fat_g": fmt(row.get("dietary_fat_g"), 0),
            }
        )

    return {
        "window_start": window_start,
        "window_end": recovery_end,
        "days_logged": int(max(calorie_days, protein_days)),
        "avg": averages,
        "latest": latest,
        "protein_target_g": protein_min,
        "protein_hit_days": int(protein_hit_days),
        "protein_hit_rate_pct": safe_pct(protein_hit_days, protein_days),
        "kcal_in_range_days": int(kcal_in_range_days),
        "kcal_in_range_rate_pct": safe_pct(kcal_in_range_days, calorie_days),
        "recent_days": recent_days,
    }


def build_plan_summary(recent: pd.DataFrame) -> dict:
    plan = pd.read_csv(PLAN_CSV)
    plan["Plan Date"] = pd.to_datetime(plan["Plan Date"])
    plan["Actual Date"] = pd.to_datetime(plan["Actual Date"], errors="coerce")
    plan_runs = plan[
        plan["Planned Workout"].str.contains("Run|Intervals|Tempo|Threshold|Long|Base|Strides|Recovery", case=False, na=False)
    ].copy()

    merged = plan_runs.merge(
        recent,
        left_on=plan_runs["Actual Date"].dt.date.astype(str),
        right_on="date",
        how="left",
        suffixes=("", "_run"),
    )
    if not merged.empty:
        merged = merged.sort_values(["Plan Date", "distance_km"], ascending=[True, False]).drop_duplicates(
            subset=["Plan Date", "Planned Workout"]
        )

    def planned_bucket(text: str) -> str:
        value = str(text).lower()
        if any(token in value for token in ["easy", "base", "recovery", "zone 2"]):
            return "easy"
        if any(token in value for token in ["tempo", "threshold"]):
            return "tempo"
        if any(token in value for token in ["interval", "stride", "vo2", "speed"]):
            return "interval"
        if "long" in value:
            return "long"
        return "other"

    merged["planned_bucket"] = merged["Planned Workout"].map(planned_bucket)

    def execution_flag(row: pd.Series) -> str:
        bucket = row["planned_bucket"]
        actual_class = row["actual_class"]
        avg_hr = row["avg_hr"]
        if pd.isna(row["Activity ID"]):
            return "no matched run"
        if bucket == "easy" and ((pd.notna(avg_hr) and avg_hr > 155) or actual_class in {"tempo/threshold", "interval/repetition", "hard/5k effort"}):
            return "too hard"
        if bucket in {"tempo", "interval"} and ((pd.notna(avg_hr) and avg_hr < 152) or actual_class in {"easy", "steady"}):
            return "too easy/blunt"
        if bucket == "long" and row["distance_km"] < 10:
            return "too short"
        return "ok/mixed"

    merged["execution_flag"] = merged.apply(execution_flag, axis=1)

    old_plan = {
        "weekly_structure": [
            "Easy runs for aerobic base",
            "Tempo runs for threshold work",
            "Interval sessions for VO2 and 5K specificity",
            "Long runs for endurance",
            "Strength work",
            "Mobility or yoga",
            "Rest days",
        ],
        "definitions": [
            "Easy = conversational, low-HR aerobic work",
            "Tempo = controlled hard, sustainable effort",
            "Intervals = short faster efforts with recovery",
            "Strides = short accelerations for turnover and mechanics",
        ],
        "execution_counts": {key: int(value) for key, value in merged["execution_flag"].value_counts().to_dict().items()},
        "matched_examples": [],
    }

    example_columns = [
        "Plan Date",
        "Planned Workout",
        "Activity Name",
        "distance_km",
        "pace_min_km",
        "avg_hr",
        "actual_class",
        "execution_flag",
    ]
    for _, row in merged[example_columns].head(12).iterrows():
        old_plan["matched_examples"].append(
            {
                "date": row["Plan Date"].date().isoformat(),
                "planned": row["Planned Workout"],
                "actual": None if pd.isna(row["Activity Name"]) else row["Activity Name"],
                "distance_km": fmt(row["distance_km"], 2),
                "pace_min_km": fmt(row["pace_min_km"], 2),
                "avg_hr": fmt(row["avg_hr"], 0),
                "actual_class": None if pd.isna(row["actual_class"]) else row["actual_class"],
                "flag": row["execution_flag"],
            }
        )
    return old_plan


def build_dashboard_data() -> dict:
    profile = load_profile()
    runs, _, recent, plan_start, plan_end = load_runs()
    recovery_end = max(
        pd.Timestamp(plan_end).date(), datetime.now().date()
    ).isoformat()
    recovery_start = (
        pd.Timestamp(recovery_end) - pd.Timedelta(days=HEALTH_LOOKBACK_DAYS - 1)
    ).date().isoformat()
    daily = load_health_daily(recovery_start, recovery_end)
    recent = recent.merge(daily, on="date", how="left")
    plan_summary = build_plan_summary(recent)

    weight_mid = 91.5
    height_cm = 183
    age = 26
    bmr = 10 * weight_mid + 6.25 * height_cm - 5 * age + 5
    active_avg = None
    if "active_kcal" in daily.columns:
        active_series = daily[["date", "active_kcal"]].dropna()
        if not active_series.empty:
            active_avg = float(active_series["active_kcal"].mean())
    maintenance_estimate = bmr + (active_avg or 850)
    maintenance_with_thermic = maintenance_estimate * 1.08
    fat_loss_floor = maintenance_with_thermic - 350
    fat_loss_ceiling = maintenance_with_thermic - 150

    protein_min = round(weight_mid * 2.0)
    protein_max = round(weight_mid * 2.2)
    fat_min = round(weight_mid * 0.8)
    fat_max = round(weight_mid * 1.0)
    nutrition_focus = build_nutrition_focus(
        daily,
        protein_min,
        fat_loss_floor,
        fat_loss_ceiling,
        recovery_end,
    )

    weekly = (
        recent.groupby("week")
        .agg(run_days=("date", "nunique"), runs=("Activity ID", "count"), km=("distance_km", "sum"), minutes=("moving_min", "sum"))
        .reset_index()
    )
    class_counts = Counter(recent["actual_class"])

    best_recent_5k = recent[recent["distance_km"].between(4.8, 5.3)].sort_values("moving_min").head(1)
    best_recent_5k_time = fmt(best_recent_5k["moving_min"].iloc[0], 2) if not best_recent_5k.empty else None
    best_recent_5k_date = best_recent_5k["date"].iloc[0] if not best_recent_5k.empty else None

    rolling_5k = recent.dropna(subset=["best5_from_splits_min"]).sort_values("best5_from_splits_min").head(1)
    best_split_5k_time = fmt(rolling_5k["best5_from_splits_min"].iloc[0], 2) if not rolling_5k.empty else None
    best_split_5k_date = rolling_5k["date"].iloc[0] if not rolling_5k.empty else None

    health_metrics = {}
    for key, digits in [
        ("steps", 0),
        ("active_kcal", 0),
        ("rhr", 1),
        ("hrv", 1),
        ("vo2max", 2),
        ("walking_hr", 1),
        ("body_mass_kg", 1),
        ("body_fat_pct", 3),
        ("sleep_hours", 1),
    ]:
        if key not in daily.columns:
            continue
        frame = daily[["date", key]].dropna()
        if frame.empty:
            continue
        health_metrics[key] = {
            "days": int(len(frame)),
            "avg": fmt(frame[key].mean(), digits),
            "latest": fmt(frame[key].iloc[-1], digits),
            "min": fmt(frame[key].min(), digits),
            "max": fmt(frame[key].max(), digits),
        }

    recent_run_rows = []
    for _, row in recent.sort_values("dt", ascending=False).head(16).iterrows():
        recent_run_rows.append(
            {
                "date": row["date"],
                "name": row["Activity Name"],
                "distance_km": fmt(row["distance_km"], 2),
                "pace_min_km": fmt(row["pace_min_km"], 2),
                "avg_hr": fmt(row["avg_hr"], 0),
                "class": row["actual_class"],
                "drift": fmt(row["hr_drift"], 1),
            }
        )

    efficiency_examples = []
    medium_runs = recent[
        recent["distance_km"].between(5, 10.5)
        & recent["avg_hr"].notna()
        & ((recent["split_pace_cv"].isna()) | (recent["split_pace_cv"] < 0.08))
    ].sort_values("dt")
    for _, row in medium_runs.iterrows():
        efficiency_examples.append(
            {
                "date": row["date"],
                "name": row["Activity Name"],
                "pace_min_km": fmt(row["pace_min_km"], 2),
                "avg_hr": fmt(row["avg_hr"], 0),
                "drift": fmt(row["hr_drift"], 1),
            }
        )

    high_share = float(recent["high_intensity"].mean()) if not recent.empty else 0.0
    easy_share = float(recent["easy_like"].mean()) if not recent.empty else 0.0
    total_runs = len(recent)
    true_5k_range = derive_5k_range(best_recent_5k_time, best_split_5k_time)

    data = {
        "meta": {
            "title": "Toni Performance Dashboard",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "analysis_window": {
                "runs_start": plan_start,
                "runs_end": plan_end,
                "recovery_start": recovery_start,
                "recovery_end": recovery_end,
            },
            "food_window": {
                "start": nutrition_focus.get("window_start"),
                "end": nutrition_focus.get("window_end"),
            },
            "watch_note": "Apple Watch data is incomplete because the watch is not worn every day. Recovery metrics only reflect days with recordings.",
        },
        "profile": profile,
        "headline": {
            "true_5k_range": true_5k_range,
            "sub20_status": "Not on current trajectory",
            "main_limiters": ["Aerobic base", "Efficiency", "Intensity distribution"],
            "best_recent_5k": {"time_min": best_recent_5k_time, "date": best_recent_5k_date},
            "best_rolling_5k": {"time_min": best_split_5k_time, "date": best_split_5k_date},
        },
        "numbers": {
            "recent_runs": total_runs,
            "recent_km": fmt(recent["distance_km"].sum(), 1),
            "recent_hours": fmt(recent["moving_min"].sum() / 60, 1),
            "high_intensity_share_pct": pct(high_share),
            "easy_like_share_pct": pct(easy_share),
            "avg_weekly_km": fmt(weekly["km"].mean(), 1),
            "avg_weekly_run_days": fmt(weekly["run_days"].mean(), 1),
        },
        "health": health_metrics,
        "run_summary": {
            "class_counts": dict(class_counts),
            "recent_runs": recent_run_rows,
            "efficiency_examples": efficiency_examples,
            "weekly": [
                {
                    "week": row["week"],
                    "run_days": int(row["run_days"]),
                    "runs": int(row["runs"]),
                    "km": fmt(row["km"], 1),
                    "minutes": fmt(row["minutes"], 1),
                }
                for _, row in weekly.iterrows()
            ],
        },
        "old_plan": plan_summary,
        "diagnosis": [
            f"Only about {pct(easy_share)}% of runs in the current {RUN_LOOKBACK_DAYS}-day block looked truly easy by HR. Most of the block still landed moderate-to-hard.",
            "Easy and recovery days repeatedly drifted into tempo effort, which undercuts aerobic development and increases knee stress.",
            "Cardiac drift was often large inside runs, a sign that aerobic durability still needs work.",
            f"The best current 5K evidence points to about {true_5k_range} shape, not sub-20 shape.",
            "Fat loss is possible with this workload, but the current pattern is too intensity-heavy for sustainable progress and muscle retention.",
        ],
        "action_flags": [
            "Base runs need to be slower and capped by HR, not ego pace.",
            "Long runs are sometimes too short and too hard.",
            "Hard days are stacked too closely in several parts of the block.",
            "The knee risk goes up when moderate fatigue turns into more pounding at medium-hard effort.",
        ],
        "body_card": {
            "name": "Toni",
            "lines": [
                "Height 183 cm",
                "Weight 90-93 kg",
                "Goal: sub-20 5K",
                "Focus: hybrid athlete",
                "Need: more true easy running",
            ],
        },
        "nutrition": {
            "bmr_estimate": fmt(bmr, 0),
            "active_kcal_corrected_avg": fmt(active_avg, 0),
            "maintenance_kcal_estimate": fmt(maintenance_with_thermic, 0),
            "fat_loss_kcal_range": [fmt(fat_loss_floor, 0), fmt(fat_loss_ceiling, 0)],
            "long_run_day_kcal_range": [3100, 3400],
            "easy_day_kcal_range": [2700, 2900],
            "protein_g_range": [protein_min, protein_max],
            "fat_g_range": [fat_min, fat_max],
            "carb_guidance": [
                "Higher carbs around Tuesday/Thursday workouts and Saturday long run",
                "Moderate carbs on easy days",
                "Do not drive calories too low on long-run or quality days",
            ],
        },
        "food_focus": nutrition_focus,
        "next_plan_constraints": [
            "Saturday long run stays in because of run club",
            "Include one home leg day",
            "Include one upper push day",
            "Include one upper pull day",
            "Plan for sub-20 progression without sacrificing muscle retention",
        ],
    }
    return data


def main() -> None:
    data = build_dashboard_data()
    payload = "window.DASHBOARD_DATA = " + json.dumps(data, indent=2) + ";\n"
    (SITE / "data.js").write_text(payload, encoding="utf-8")
    print(f"Wrote {SITE / 'data.js'}")


if __name__ == "__main__":
    main()
