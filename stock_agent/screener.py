from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Optional
import math

from .providers import TickerSnapshot


@dataclass
class ScoredTicker:
    snapshot: TickerSnapshot
    score_total: float
    scores: Dict[str, float]


def _zscore(values: List[Optional[float]], invert: bool = False) -> List[float]:
    cleaned: List[Optional[float]] = [v if v is not None and math.isfinite(v) else None for v in values]
    # compute mean ignoring None
    finite_vals = [v for v in cleaned if v is not None]
    if not finite_vals:
        return [0.0 for _ in values]
    mean = sum(finite_vals) / len(finite_vals)
    var = sum((v - mean) ** 2 for v in finite_vals) / len(finite_vals)
    std = math.sqrt(var) if var > 0 else 1.0
    z = []
    for v in cleaned:
        if v is None:
            z.append(0.0)
        else:
            z.append((v - mean) / std)
    if invert:
        z = [-x for x in z]
    return [float(x) for x in z]


def rank_tickers(
    snapshots: List[TickerSnapshot],
    weights: Optional[Dict[str, float]] = None,
    min_market_cap: Optional[float] = None,
) -> List[ScoredTicker]:
    if weights is None:
        weights = {
            "value": 0.25,      # lower PE is better
            "quality": 0.25,    # higher gross margin is better
            "growth": 0.30,     # higher revenue CAGR is better
            "momentum": 0.20,   # higher 6m return is better, penalize high vol
        }

    filtered = [s for s in snapshots if (min_market_cap is None or (s.market_cap or 0) >= min_market_cap)]

    pe = [s.pe_trailing if s.pe_trailing and s.pe_trailing > 0 else None for s in filtered]
    gross_margin = [s.gross_margin for s in filtered]
    cagr = [s.revenue_cagr_3y for s in filtered]
    ret6 = [s.returns_6m for s in filtered]
    vol = [s.volatility_1y for s in filtered]

    z_value = _zscore(pe, invert=True)  # lower PE better
    z_quality = _zscore(gross_margin)
    z_growth = _zscore(cagr)
    z_mom_ret = _zscore(ret6)
    z_mom_vol = _zscore(vol, invert=True)  # lower vol better

    scored: List[ScoredTicker] = []
    for i, s in enumerate(filtered):
        value = z_value[i]
        quality = z_quality[i]
        growth = z_growth[i]
        momentum = 0.7 * z_mom_ret[i] + 0.3 * z_mom_vol[i]
        total = (
            weights.get("value", 0) * value +
            weights.get("quality", 0) * quality +
            weights.get("growth", 0) * growth +
            weights.get("momentum", 0) * momentum
        )
        scored.append(ScoredTicker(snapshot=s, score_total=float(total), scores={
            "value": float(value),
            "quality": float(quality),
            "growth": float(growth),
            "momentum": float(momentum),
        }))

    scored.sort(key=lambda x: x.score_total, reverse=True)
    return scored