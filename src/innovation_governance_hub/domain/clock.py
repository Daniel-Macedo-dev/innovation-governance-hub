from datetime import date

from innovation_governance_hub.config import get_settings


def business_date() -> date:
    """Return the controllable date used by business rules.

    Audit timestamps deliberately continue using the real clock.
    """
    return get_settings().demo_reference_date or date.today()
