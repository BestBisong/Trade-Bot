import datetime
import json
import os


DEFAULT_PARAMS = {
    "ml_conf_long_trending": 0.57,
    "ml_conf_long_ranging": 0.60,
    "ml_conf_short_trending": 0.43,
    "ml_conf_short_ranging": 0.40,
    "atr_min_pct": 0.0015,
    "stop_atr_scale": 1.00,
}

SAFETY_BOUNDS = {
    "ml_conf_long_trending": (0.54, 0.70),
    "ml_conf_long_ranging": (0.56, 0.74),
    "ml_conf_short_trending": (0.30, 0.46),
    "ml_conf_short_ranging": (0.26, 0.44),
    "atr_min_pct": (0.0010, 0.0040),
    "stop_atr_scale": (0.85, 1.25),
}


def _clamp(value, key):
    low, high = SAFETY_BOUNDS[key]
    return max(low, min(high, value))


def _safe_read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            content = f.read().strip()
            if not content:
                return default
            return json.loads(content)
    except Exception:
        return default


def _safe_write_json(path, payload):
    with open(path, "w") as f:
        json.dump(payload, f, default=str, indent=2)


def _merge_with_defaults(params):
    out = dict(DEFAULT_PARAMS)
    if isinstance(params, dict):
        out.update(params)
    for key in list(out.keys()):
        if key in SAFETY_BOUNDS:
            out[key] = _clamp(float(out[key]), key)
    return out


def load_tuned_params(path="tuned_params.json"):
    raw = _safe_read_json(path, {})
    params = _merge_with_defaults(raw.get("params", {}))
    return {
        "params": params,
        "updated_at": raw.get("updated_at"),
        "next_review_at": raw.get("next_review_at"),
        "last_metrics": raw.get("last_metrics", {}),
        "action": raw.get("action", "initial"),
    }


def _is_due_for_review(updated_at, review_days=7):
    if not updated_at:
        return True
    try:
        ts = datetime.datetime.fromisoformat(updated_at)
        return (datetime.datetime.utcnow() - ts).days >= review_days
    except Exception:
        return True


def tune_from_walk_forward(metrics, current_params):
    params = dict(current_params)

    win_rate = float(metrics.get("win_rate", 0.0))
    avg_pnl = float(metrics.get("avg_window_pnl", 0.0))
    worst_dd = float(metrics.get("worst_drawdown_pct", 100.0))

    action = "hold"

    # Poor quality: move thresholds toward 0.5 together (never push long to 0.62 and short to 0.38)
    if win_rate < 52.0 or avg_pnl < 0:
        params["ml_conf_long_trending"] = min(params["ml_conf_long_trending"] + 0.01, 0.58)
        params["ml_conf_long_ranging"] = min(params["ml_conf_long_ranging"] + 0.01, 0.58)
        params["ml_conf_short_trending"] = max(params["ml_conf_short_trending"] - 0.01, 0.42)
        params["ml_conf_short_ranging"] = max(params["ml_conf_short_ranging"] - 0.01, 0.42)
        params["atr_min_pct"] += 0.0002
        params["stop_atr_scale"] += 0.03
        action = "tighten"

    # Strong quality regime: allow slightly more participation.
    elif win_rate > 58.0 and avg_pnl > 0 and worst_dd < 8.0:
        params["ml_conf_long_trending"] -= 0.005
        params["ml_conf_long_ranging"] -= 0.005
        params["ml_conf_short_trending"] += 0.005
        params["ml_conf_short_ranging"] += 0.005
        params["atr_min_pct"] -= 0.0001
        params["stop_atr_scale"] -= 0.02
        action = "loosen"

    for key in SAFETY_BOUNDS:
        params[key] = _clamp(float(params[key]), key)

    return params, action


def maybe_update_weekly_tuning(report, path="tuned_params.json", review_days=7):
    state = load_tuned_params(path)
    params = state["params"]

    if not _is_due_for_review(state.get("updated_at"), review_days=review_days):
        return {
            "updated": False,
            "state": state,
        }

    agg = report.get("aggregate", {}) if isinstance(report, dict) else {}
    tuned, action = tune_from_walk_forward(agg, params)

    now = datetime.datetime.utcnow()
    next_review = now + datetime.timedelta(days=review_days)
    new_state = {
        "params": tuned,
        "updated_at": now.isoformat(),
        "next_review_at": next_review.isoformat(),
        "last_metrics": {
            "win_rate": float(agg.get("win_rate", 0.0)),
            "avg_window_pnl": float(agg.get("avg_window_pnl", 0.0)),
            "worst_drawdown_pct": float(agg.get("worst_drawdown_pct", 100.0)),
            "total_windows": int(agg.get("total_windows", 0)),
        },
        "action": action,
    }
    _safe_write_json(path, new_state)

    return {
        "updated": True,
        "state": new_state,
    }
