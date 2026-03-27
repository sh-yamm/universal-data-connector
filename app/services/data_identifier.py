from typing import List, Dict


# Sniffs the shape of the data by peeking at the first record's keys.
# This lets business_rules and voice_optimizer apply the right logic
# without needing to know which connector produced the data.
def identify_data_type(data: List[Dict]) -> str:
    if not data:
        return "empty"
    if "date" in data[0]:         # analytics records have a "date" field
        return "time_series"
    if "ticket_id" in data[0]:    # support records have "ticket_id"
        return "tabular_support"
    if "customer_id" in data[0]:  # CRM records have "customer_id"
        return "tabular_crm"
    return "unknown"
