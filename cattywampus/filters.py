from datetime import date, datetime

import pytz

def format_time(date):
    # return date.strftime('%d %b %Y %H:%M:%S')
    return date.strftime('%H:%M:%S')

def format_date(date):
    return date.strftime('%d %b %Y')

def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.

    http://flask.pocoo.org/snippets/33/
    """
    if not isinstance(dt, (datetime, date)):
        return dt
    now = datetime.utcnow().replace(tzinfo=pytz.utc)
    diff = now - dt
    
    periods = (
        (diff.days // 365, "year", "years"),
        (diff.days // 30, "month", "months"),
        (diff.days // 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds // 3600, "hour", "hours"),
        (diff.seconds // 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:
        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)
    return default

def bytes_to_human(_bytes):
    """Format number of bytes to a readable file size (e.g. 10.1 MB,
    13 kB, etc.)"""
    _bytes = float(_bytes)
    for units in ['B', 'K', 'M', 'GB', 'TB']:
        if _bytes < 1000.:
            return "{:.0f} {:>2}".format(_bytes, units)
        _bytes /= 1000.
    # if number of bytes is way too big just use petabytes
    return "{:,.0f} {:>2}".format(_bytes, "PB")
