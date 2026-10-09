"""Deterministic portfolio-overlap analytics for verified stored disclosures."""

from __future__ import annotations

import re
from dataclasses import asdict

from src.portfolios import (
    BY_ID,
    Holding,
    PortfolioSnapshot,
    compare_portfolios,
    disclosure_freshness,
)

MAX_NETWORK_SECURITIES = 40


def security_identity(holding: Holding) -> str | None:
    """Return a class-aware identifier; never infer an overlap from ticker alone."""
    cusip = re.sub(r"[^A-Z0-9]", "", holding.cusip.upper())
    if not cusip:
        return None
    security_class = re.sub(r"\s+", " ", holding.security_class.upper()).strip()
    return f"{cusip}|{security_class}|{holding.put_call.upper()}|{holding.share_type.upper()}"


def _snapshot_for_period(
    snapshots: list[PortfolioSnapshot], period: str | None
) -> PortfolioSnapshot | None:
    if not snapshots:
        return None
    if not period:
        return snapshots[0]
    return next(
        (snapshot for snapshot in snapshots if snapshot.reporting_period <= period),
        None,
    )


def _holding_map(snapshot: PortfolioSnapshot) -> dict[str, Holding]:
    result: dict[str, Holding] = {}
    for holding in snapshot.holdings:
        identity = security_identity(holding)
        if identity is None:
            continue
        old = result.get(identity)
        if old is None:
            result[identity] = Holding(**asdict(holding))
        else:
            old.shares += holding.shares
            old.reported_value += holding.reported_value
            old.weight += holding.weight
    return result


def analyze_overlap(
    snapshots_by_institution: dict[str, list[PortfolioSnapshot]],
    period: str | None = None,
) -> dict:
    """Compare 2–5 institutions using their latest disclosure at/before period."""
    if not 2 <= len(snapshots_by_institution) <= 5:
        raise ValueError("Select between 2 and 5 institutions.")

    ordered_ids = list(snapshots_by_institution)
    selected: dict[str, PortfolioSnapshot] = {}
    unavailable: list[str] = []
    for institution_id in ordered_ids:
        snapshot = _snapshot_for_period(
            snapshots_by_institution[institution_id], period
        )
        if snapshot is None:
            unavailable.append(institution_id)
        else:
            selected[institution_id] = snapshot

    maps = {key: _holding_map(snapshot) for key, snapshot in selected.items()}
    sets = [set(rows) for rows in maps.values()]
    union = set().union(*sets) if sets else set()
    intersection = (
        set.intersection(*sets) if sets and len(sets) == len(ordered_ids) else set()
    )
    shared = {
        identity
        for identity in union
        if sum(identity in rows for rows in maps.values()) >= 2
    }
    jaccard = len(intersection) / len(union) if union else 0.0
    weight_overlap = (
        sum(
            min(maps[key][identity].weight for key in ordered_ids)
            for identity in intersection
        )
        if intersection and all(key in maps for key in ordered_ids)
        else 0.0
    )

    pairwise = []
    for index, left in enumerate(ordered_ids):
        for right in ordered_ids[index + 1 :]:
            comparable = left in maps and right in maps
            if not comparable:
                pairwise.append(
                    {
                        "left": left,
                        "right": right,
                        "comparable": False,
                        "shared_count": None,
                        "jaccard": None,
                        "weight_overlap": None,
                    }
                )
                continue
            left_set, right_set = set(maps.get(left, {})), set(maps.get(right, {}))
            pair_union = left_set | right_set
            pair_shared = left_set & right_set
            pairwise.append(
                {
                    "left": left,
                    "right": right,
                    "comparable": True,
                    "shared_count": len(pair_shared),
                    "jaccard": len(pair_shared) / len(pair_union)
                    if pair_union
                    else 0.0,
                    "weight_overlap": sum(
                        min(maps[left][identity].weight, maps[right][identity].weight)
                        for identity in pair_shared
                    ),
                }
            )

    history_rows = []
    for institution_id in ordered_ids:
        institution = BY_ID.get(institution_id)
        for snapshot in snapshots_by_institution[institution_id][:8]:
            mapped = _holding_map(snapshot)
            weights = sorted(
                (holding.weight for holding in mapped.values()), reverse=True
            )
            history_rows.append(
                {
                    "institution_id": institution_id,
                    "institution_name": institution.name
                    if institution
                    else institution_id,
                    "reporting_period": snapshot.reporting_period,
                    "source_type": snapshot.source_type,
                    "holding_count": len(snapshot.holdings),
                    "mapped_count": len(mapped),
                    "disclosed_value_total": sum(
                        holding.reported_value for holding in snapshot.holdings
                    ),
                    "top_five_weight": sum(weights[:5]),
                }
            )

    security_rows = []
    for identity in union:
        owners = []
        representative = next(
            rows[identity] for rows in maps.values() if identity in rows
        )
        for institution_id in ordered_ids:
            holding = maps.get(institution_id, {}).get(identity)
            if holding:
                owners.append(
                    {
                        "institution_id": institution_id,
                        "shares": holding.shares,
                        "reported_value": holding.reported_value,
                        "weight": holding.weight,
                    }
                )
        security_rows.append(
            {
                "id": identity,
                "ticker": representative.ticker,
                "issuer": representative.issuer,
                "cusip": representative.cusip,
                "security_class": representative.security_class,
                "put_call": representative.put_call,
                "owner_count": len(owners),
                "owners": owners,
                "combined_weight": sum(owner["weight"] for owner in owners),
            }
        )
    security_rows.sort(
        key=lambda row: (row["owner_count"], row["combined_weight"], row["issuer"]),
        reverse=True,
    )
    network_securities = security_rows[:MAX_NETWORK_SECURITIES]
    network_ids = {row["id"] for row in network_securities}

    institutions = []
    changes = []
    for institution_id in ordered_ids:
        institution = BY_ID.get(institution_id)
        snapshot = selected.get(institution_id)
        if not snapshot:
            institutions.append(
                {
                    "id": institution_id,
                    "name": institution.name if institution else institution_id,
                    "available": False,
                    "holding_count": 0,
                    "mapped_count": 0,
                    "unmapped_count": 0,
                    "unique_count": 0,
                }
            )
            continue
        rows = maps[institution_id]
        institutions.append(
            {
                "id": institution_id,
                "name": institution.name if institution else institution_id,
                "investor": institution.investor if institution else "",
                "available": True,
                "holding_count": len(snapshot.holdings),
                "mapped_count": len(rows),
                "unmapped_count": len(snapshot.holdings) - len(rows),
                "unique_count": sum(
                    1
                    for identity in rows
                    if sum(identity in item for item in maps.values()) == 1
                ),
                "reporting_period": snapshot.reporting_period,
                "filing_date": snapshot.filing_date,
                "source_url": snapshot.source_url,
                "source_type": snapshot.source_type,
                "freshness": disclosure_freshness(
                    snapshot.reporting_period, source_type=snapshot.source_type
                ),
            }
        )
        history = snapshots_by_institution[institution_id]
        current_index = history.index(snapshot)
        if current_index + 1 < len(history):
            previous = history[current_index + 1]
            if previous.source_type == snapshot.source_type:
                for change in compare_portfolios(previous, snapshot):
                    if change["activity"] != "UNCHANGED":
                        changes.append(
                            {
                                "institution_id": institution_id,
                                **change,
                                "pct_change": change["share_change_pct"],
                            }
                        )

    periods = sorted(
        {
            snapshot.reporting_period
            for snapshots in snapshots_by_institution.values()
            for snapshot in snapshots[:8]
        },
        reverse=True,
    )[:24]
    source_types = {snapshot.source_type for snapshot in selected.values()}
    coverage_notes = [
        "Overlap means the same verified CUSIP, security class, option designation, and share type; it does not imply shared investment intent.",
        "13F filings are delayed and incomplete and omit many assets and hedges. Values reflect disclosed positions, not current exposure.",
        "Original 13F-HR snapshots are compared; amendments are not silently consolidated.",
    ]
    if len({snapshot.reporting_period for snapshot in selected.values()}) > 1:
        coverage_notes.append(
            "Institutions have different available reporting dates; each uses its latest stored disclosure at or before the selected date."
        )
    if len(source_types) > 1:
        coverage_notes.append(
            "Coverage mixes disclosure types (for example, daily fund holdings and quarterly 13F); compare dates and scope before interpreting overlap."
        )
    if unavailable:
        coverage_notes.append(
            "No eligible stored snapshot was available for: "
            + ", ".join(unavailable)
            + "."
        )
    unmapped = sum(institution.get("unmapped_count", 0) for institution in institutions)
    if unmapped:
        coverage_notes.append(
            f"{unmapped} holding row(s) lacked a usable class-aware CUSIP identity and were excluded from overlap metrics."
        )

    return {
        "requested_period": period,
        "periods": periods,
        "institutions": institutions,
        "securities": security_rows,
        "network": {
            "securities": network_securities,
            "truncated": len(security_rows) > len(network_securities),
            "security_limit": MAX_NETWORK_SECURITIES,
            "edges": [
                {
                    "institution_id": owner["institution_id"],
                    "security_id": row["id"],
                    **owner,
                }
                for row in network_securities
                for owner in row["owners"]
                if row["id"] in network_ids
            ],
        },
        "summary": {
            "common_count": len(intersection),
            "shared_count": len(shared),
            "union_count": len(union),
            "jaccard": jaccard,
            "weight_overlap": weight_overlap,
        },
        "pairwise": pairwise,
        "history": history_rows,
        "changes": changes,
        "coverage_notes": coverage_notes,
    }
