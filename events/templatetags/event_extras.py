from django import template

register = template.Library()


@register.filter
def month_short(value):
    """Return month in short uppercase format (e.g., 'JAN')."""
    if not value:
        return ''
    return value.strftime('%b').upper()


@register.filter
def day_number(value):
    """Return day number with leading zero (e.g., '02')."""
    if not value:
        return ''
    return value.strftime('%d')


@register.filter
def year_number(value):
    """Return year (e.g., '2025')."""
    if not value:
        return ''
    return value.strftime('%Y')
