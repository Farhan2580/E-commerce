"""Build option controls only when their attributes identify one exact SKU."""
SWATCHES = {'black': '#2d3540', 'night sky': '#2d3540', 'white': '#f4f3ef',
            'star white': '#f4f3ef', 'blue': '#45698c', 'red': '#b84746',
            'green': '#627d67', 'silver': '#c6cbd0', 'gold': '#cbb890',
            'pink': '#dfb8c6', 'purple': '#9b89b3', 'gray': '#7b8187', 'grey': '#7b8187'}


def option_groups(variants):
    variants = list(variants)
    fields = [('color', 'Color'), ('storage', 'Storage'), ('ram', 'RAM'), ('size', 'Size'), ('warranty', 'Warranty')]
    fields = [(field, label) for field, label in fields if variants and all(getattr(v, field).strip() for v in variants)]
    if not fields or len({tuple(getattr(v, field) for field, _ in fields) for v in variants}) != len(variants):
        return []
    return [{'field': field, 'label': label,
             'values': [{'name': value, 'swatch': SWATCHES.get(value.casefold(), '') if field == 'color' else ''}
                        for value in dict.fromkeys(getattr(v, field) for v in variants)]}
            for field, label in fields]
