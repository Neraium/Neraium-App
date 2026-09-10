"""App mapping policy driven exclusively by pinned authority preview classifications."""
from . import authority

EXCLUSION_REASON = "unsupported_cumulative_counter_for_paired_analysis"
# This exact authority revision's supplied_reference.py explicitly rejects counters.
# A future pin must be reviewed before extending this policy.
COUNTER_UNSUPPORTED_COMMIT = "b790479f0abcb90aa71f7677d10aa542222b55c8"


def exclude_unsupported_counters(value, mapping, response, input_sha256):
    identity = response["identity"]
    if (value.get("mode") != "paired"
            or identity.get("commit") != COUNTER_UNSUPPORTED_COMMIT
            or identity.get("adapter_contract") != authority.CONTRACT):
        return []
    catalog = response["catalog"]
    exclusions = []
    previous = value.get("preview", {})
    previous_signals = {s["column"]: s for s in value.get("mapping", {}).get("signals", [])}
    for signal in mapping["signals"]:
        if not signal["include"]:
            # Reuse only server-stored evidence for an unchanged excluded mapping.
            # Source replacement/revalidation already invalidates mapping and preview.
            if previous.get("identity") == identity and previous_signals.get(signal["column"]) == signal:
                exclusions.extend(e for e in previous.get("exclusions", []) if e["column"] == signal["column"])
            continue
        name = signal["meaning"].strip()
        classifications = {role: catalog.get(role, {}).get(name, {}) for role in ("reference", "comparison")}
        if not all(c.get("telemetry_category") == "cumulative_counter" for c in classifications.values()):
            continue
        signal.update(include=False, reason=EXCLUSION_REASON)
        exclusions.append({"column": signal["column"], "classification": "cumulative_counter",
                           "excluded_from": "paired_analysis", "reason": EXCLUSION_REASON,
                           "authority_classifications": classifications, "identity": identity,
                           "classification_input_sha256": input_sha256})
    return exclusions
