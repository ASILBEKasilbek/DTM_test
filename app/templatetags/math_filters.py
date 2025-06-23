from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """Qiymatni bo‘lish"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """Qiymatni ko‘paytirish"""
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0
