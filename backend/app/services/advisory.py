def build_advisory(
    predictions: list[dict],
    scenario: dict,
    route_corridors: list[str] | None = None,
) -> dict:
    route_specific = route_corridors is not None
    eligible = [
        item for item in predictions
        if not route_specific or item["corridor"] in route_corridors
    ]
    ranked = sorted(eligible, key=lambda item: item["severity_score"], reverse=True)
    high = [item for item in ranked if item["risk"] == "HIGH"]
    for item in ranked:
        actions = ["Normal monitoring"]
        if item["risk"] == "HIGH":
            actions = ["Deploy additional traffic personnel", "Prepare diversion route", "Issue commuter advisory"]
            if scenario.get("roadwork"):
                actions.append("Coordinate or pause non-critical roadwork")
            if scenario.get("weather", "").lower() == "rain":
                actions.append("Enhance incident monitoring")
        elif item["risk"] == "MEDIUM":
            actions = ["Monitor corridor", "Prepare standby personnel", "Review diversion readiness"]
        item["actions"] = actions
        item["triggered_rules"] = [f"{item['risk']} severity threshold", *item["factors"]]
    counts = {risk: sum(item["risk"] == risk for item in ranked) for risk in ("HIGH", "MEDIUM", "LOW")}
    direction = predictions[0].get("travel_direction", "LOCAL") if predictions else "LOCAL"
    directional_note = (
        "No route-specific corridor recommendation is available for this route."
        if route_specific and not ranked else
        "Prioritize outbound corridors because the scenario indicates a weekend/festival outbound surge."
        if direction == "OUTBOUND" else
        "Prioritize inbound corridors because the scenario indicates a post-holiday return surge."
        if direction == "INBOUND" else
        "Use normal local monitoring because no major directional surge was detected."
    )
    summary = (
        f"{len(high)} high-risk route corridor(s) identified for this route"
        if route_specific and ranked else
        "No reliable matched corridor is available for this route"
        if route_specific else
        f"{len(high)} high-risk corridors identified for the scenario"
    )
    return {"high_priority_corridors": high, "corridors": ranked, "counts": counts,
            "summary": summary, "scope": "route" if route_specific else "citywide",
            "travel_direction": direction, "directional_note": directional_note}
