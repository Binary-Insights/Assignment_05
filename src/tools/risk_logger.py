from datetime import date
from pydantic import BaseModel, HttpUrl

class LayoffSignal(BaseModel):
    """Structured description of a potential layoff / risk signal."""
    company_id: str
    occurred_on: date
    description: str
    source_url: HttpUrl

async def report_layoff_signal(signal_data: LayoffSignal) -> bool:
    """
    Tool: report_layoff_signal

    Record a high-risk layoff / workforce reduction / negative event for the given company.

    This tool is intended to be destructive / side-effectful:
    - write to a log file,
    - send an alert,
    - or mark the company in a risk database.

    Args:
        signal_data: LayoffSignal with company_id, occurred_on, description, and source_url.

    Returns:
        True if logging succeeded, False otherwise.

    NOTE: Implement your own logging / persistence here.
    """
    # TODO: implement real logging
    print(f"[RISK LOGGER] {signal_data.company_id} - {signal_data.occurred_on} - {signal_data.description} ({signal_data.source_url})")
    return True