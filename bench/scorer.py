import math
from datetime import datetime, timedelta
from typing import Any

from backend.common.time import parse_timestamp
from backend.ledger.records import order_key
from backend.ml.causal.graph import event_node

from .faults.catalogue import Fault


def matches(
    event: dict[str, Any], signature: dict[str, Any], trace: list[dict[str, Any]] | None = None
) -> bool:
    if event["type"] != signature["type"] or event_node(event) != signature["node"]:
        return False
    condition = signature["condition"]
    if "status" in condition and event["status"] != condition["status"]:
        return False
    if "duration_ms_gt" in condition and event["duration_ms"] <= condition["duration_ms_gt"]:
        return False
    if any(
        event["attributes"].get(key) != value
        for key, value in condition.get("attribute_equals", {}).items()
    ):
        return False
    return _trace_conditions(trace or [event], condition)


def score_scenario(
    fault: Fault,
    injection_time: datetime,
    events: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    reports: list[dict[str, Any]],
) -> dict[str, Any]:
    traces: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        traces.setdefault(event["trace_id"], []).append(event)
    affected = sorted(
        (
            event
            for event in events
            if parse_timestamp(event["ended_at"]) >= injection_time
            and matches(event, fault.signature, traces.get(event["trace_id"]))
        ),
        key=order_key,
    )
    truth = affected[0] if affected else None
    relevant = sorted(
        (
            incident
            for incident in incidents
            if parse_timestamp(incident["opened_at"]) >= injection_time
        ),
        key=lambda incident: incident["opened_at"],
    )
    incident = relevant[0] if relevant else None
    report = next(
        (
            report
            for report in reports
            if incident and str(report["incident_id"]) == str(incident["id"])
        ),
        None,
    )
    start_id = str(incident.get("start_event_id")) if incident else None
    span_by_event = {str(event["event_id"]): event["span_id"] for event in events}
    exact = (
        truth is not None
        and incident is not None
        and (start_id == truth["event_id"] or span_by_event.get(start_id) == truth["span_id"])
    )
    return {
        "bug_id": fault.id,
        "control": fault.rag_split == "control",
        "ground_truth_event": truth["event_id"] if truth else None,
        "detected": incident is not None,
        "exact_start": exact,
        "detection_delay_seconds": (
            parse_timestamp(incident["opened_at"]) - injection_time
        ).total_seconds()
        if incident
        else None,
        "root_cause_correct": report["report"]["report"]["root_cause_node"]
        == fault.ground_truth_node
        if report
        else None,
        "evidence_count": len(set(report["report"]["report"]["evidence_ids"])) if report else 0,
        "rca_source": report["source"] if report else None,
        "time_to_rca_seconds": (
            parse_timestamp(report["created_at"]) - injection_time
        ).total_seconds()
        if report
        else None,
        "failure": None
        if exact
        else "no_matching_ground_truth"
        if truth is None
        else "not_detected"
        if incident is None
        else "start_event_mismatch",
    }


def false_positive_rate(
    normal_start: datetime, normal_end: datetime, incident_times: list[datetime]
) -> dict[str, Any]:
    windows = math.floor((normal_end - normal_start).total_seconds() / 3600)
    false = sum(
        any(
            normal_start + timedelta(hours=index) <= at < normal_start + timedelta(hours=index + 1)
            for at in incident_times
        )
        for index in range(windows)
    )
    return {
        "windows": windows,
        "false_windows": false,
        "rate": false / windows if windows else None,
    }


def _operation_matches(event: dict[str, Any], operation: dict[str, Any]) -> bool:
    return event["type"] == operation["type"] and (
        "downstream_service" not in operation
        or event["attributes"].get("downstream_service") == operation["downstream_service"]
    )


def _trace_conditions(trace: list[dict[str, Any]], condition: dict[str, Any]) -> bool:
    if operation := condition.get("missing_operation"):
        if any(_operation_matches(event, operation) for event in trace):
            return False
    if operation := condition.get("operation_count"):
        if sum(_operation_matches(event, operation) for event in trace) < operation["minimum"]:
            return False
    if order := condition.get("call_order"):
        calls = [
            event["attributes"]["downstream_service"]
            for event in sorted(trace, key=lambda event: event["timestamp"])
            if event["type"] == "http.client"
        ]
        if any(service not in calls for service in order):
            return False
        return calls.index(order[0]) < calls.index(order[1])
    return True
