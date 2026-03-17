import calendar
from datetime import date
from typing import Optional

import holidays


def get_brazil_holidays(year: int) -> set[date]:
    br_holidays = holidays.Brazil(years=year, state="PB")
    return set(br_holidays.keys())


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    
    br_holidays = get_brazil_holidays(d.year)
    return d not in br_holidays


def get_nth_business_day(year: int, month: int, n: int = 5) -> date:
    business_day_count = 0
    day = 1
    max_day = calendar.monthrange(year, month)[1]
    
    while business_day_count < n and day <= max_day:
        current_date = date(year, month, day)
        if is_business_day(current_date):
            business_day_count += 1
            if business_day_count == n:
                return current_date
        day += 1
    
    raise ValueError(f"Could not find {n}th business day in {year}-{month:02d}")


def is_nth_business_day(d: Optional[date] = None, n: int = 5) -> bool:
    if d is None:
        d = date.today()
    
    try:
        nth_business_day = get_nth_business_day(d.year, d.month, n)
        return d == nth_business_day
    except ValueError:
        return False


def get_month_name_pt(month: int) -> str:
    months = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }
    return months.get(month, "")


def get_current_month_column() -> str:
    today = date.today()
    month_name = get_month_name_pt(today.month)
    return month_name


def get_months_up_to_current() -> list[str]:
    """Return ordered list of month names from Janeiro up to (and including) the current month."""
    today = date.today()
    return [get_month_name_pt(m) for m in range(1, today.month + 1)]


def get_unpaid_months(payment_status: dict[str, str], current_month: str) -> list[str]:
    """Return list of months (before current) where the member hasn't paid."""
    all_months = get_months_up_to_current()

    unpaid = []
    for month in all_months:
        if month == current_month:
            continue
        status = str(payment_status.get(month, "")).strip().lower()
        if status not in ("paid", "pago"):
            unpaid.append(month)
    return unpaid
