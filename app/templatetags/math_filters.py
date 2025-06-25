from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    return dictionary.get(str(key)) if dictionary else None

@register.filter
def div(value, arg):
    """Qiymatni bo‘lish"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0

@register.filter
def mul(value, arg):
    """Qiymatni ko‘paytirish"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
