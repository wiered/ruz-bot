from datetime import datetime, timedelta, date, time

def getStartEndOfDay(target_date: date) -> tuple:
    """
    Returns the start and end of the day relative to the given target date.

    Args:
        target_date (date): The target date

    Returns:
        tuple: A tuple containing the start and end of the day
    """
    # Get the start of the day
    start_of_day = datetime.combine(target_date, time.min)
    
    # Get the end of the day
    end_of_day = datetime.combine(target_date, time.max)
    
    # Return the start and end of the day
    return start_of_day, end_of_day


def getStartAndEndOfWeek(reference_date: datetime) -> tuple:
    """
    Returns the start and end of the week relative to the given reference date.

    Args:
        reference_date (datetime): The reference date

    Returns:
        tuple: A tuple containing the start and end of the week
    """
    # Start of the week (Monday)
    start_of_week = reference_date - timedelta(days=reference_date.weekday())
    # End of the week (Sunday)
    _, end_of_week = getStartEndOfDay(start_of_week + timedelta(days=5))
    
    # Get the start of the day of the first day of the week
    start_of_week, _ = getStartEndOfDay(start_of_week)
    return start_of_week, end_of_week


def getPreviousAndNextMonthBounds(reference_date: datetime):
    """
    Returns the start of the previous month and the end of the next month
    relative to the given reference date.

    Args:
        reference_date (datetime): The reference date

    Returns:
        tuple: A tuple containing the start of the previous month and the end of the next month
    """
    # Step 1: Start of the previous month
    first_day_of_current_month = reference_date.replace(day=1)
    start_of_previous_month = first_day_of_current_month - timedelta(days=1)
    # Get the start of the day of the first day of the previous month
    start_of_previous_month, _ = getStartEndOfDay(start_of_previous_month.replace(day=1))

    # Step 2: End of the next month
    first_day_of_next_next_month = (first_day_of_current_month + timedelta(days=31)).replace(day=1)
    end_of_next_month = (first_day_of_next_next_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    # Get the end of the day of the last day of the next month
    _, end_of_next_month = getStartEndOfDay(end_of_next_month)

    return start_of_previous_month, end_of_next_month