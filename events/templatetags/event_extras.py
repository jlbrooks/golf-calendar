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


def _get_tour_color_base(tour_name):
    """Map tour name to color base (e.g., 'blue', 'pink')."""
    if not tour_name:
        return 'gray'
    
    tour_name_upper = tour_name.upper()
    # Check LPGA first since it contains 'PGA'
    if 'LPGA' in tour_name_upper:
        return 'pink'
    elif 'PGA' in tour_name_upper and 'TOUR' in tour_name_upper:
        return 'blue'
    elif 'KORN FERRY' in tour_name_upper:
        return 'emerald'
    elif 'LIV' in tour_name_upper:
        return 'slate'
    elif 'DP WORLD' in tour_name_upper:
        return 'purple'
    else:
        return 'gray'


@register.filter
def tour_color_accent(tour_name):
    """Return Tailwind color class for accent bar (e.g., 'bg-blue-500')."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-500'


@register.filter
def tour_color_border(tour_name):
    """Return Tailwind color class for border (e.g., 'border-blue-400')."""
    color_base = _get_tour_color_base(tour_name)
    return f'border-{color_base}-400'


@register.filter
def tour_color_bg(tour_name):
    """Return Tailwind color class for background (e.g., 'bg-blue-50/30')."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-50/30'


@register.filter
def tour_color_bg_solid(tour_name):
    """Return Tailwind color class for solid background (e.g., 'bg-blue-50')."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-50'


@register.filter
def tour_color_text(tour_name):
    """Return Tailwind color class for text (e.g., 'text-blue-700')."""
    color_base = _get_tour_color_base(tour_name)
    return f'text-{color_base}-700'


@register.filter
def tour_color_button_hover(tour_name):
    """Return Tailwind color classes for button hover state."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-600 text-white border-{color_base}-600'


@register.filter
def tour_color_button_hover_light(tour_name):
    """Return Tailwind color classes for button light hover state."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-50 text-{color_base}-700 border-{color_base}-200'


@register.filter
def tour_color_border_hover(tour_name):
    """Return Tailwind color class for hover border (e.g., 'hover:border-blue-400')."""
    color_base = _get_tour_color_base(tour_name)
    return f'hover:border-{color_base}-400'


@register.filter
def tour_color_text_hover(tour_name):
    """Return Tailwind color class for hover text (e.g., 'group-hover:text-blue-700')."""
    color_base = _get_tour_color_base(tour_name)
    return f'group-hover:text-{color_base}-700'


@register.filter
def tour_color_button_hover_classes(tour_name):
    """Return Tailwind color classes for button hover state with hover prefix."""
    color_base = _get_tour_color_base(tour_name)
    return f'hover:bg-{color_base}-50 hover:text-{color_base}-700 hover:border-{color_base}-200'


@register.filter
def tour_color_button_group_hover_classes(tour_name):
    """Return Tailwind color classes for button group-hover state."""
    color_base = _get_tour_color_base(tour_name)
    return f'group-hover:bg-{color_base}-600 group-hover:text-white group-hover:border-{color_base}-600'


@register.filter
def tour_color_badge(tour_name):
    """Return Tailwind color classes for tour badge (background, text, border)."""
    color_base = _get_tour_color_base(tour_name)
    return f'bg-{color_base}-50 text-{color_base}-700 border-{color_base}-200'
