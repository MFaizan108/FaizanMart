from django.utils.text import slugify


def unique_slugify(instance, value, slug_field="slug", max_length=200):
    """Generate a unique slug for `instance` from `value`, appending -1, -2, ... on collision."""
    model = type(instance)
    base_slug = slugify(value)[:max_length]
    slug = base_slug
    counter = 1
    while model.objects.filter(**{slug_field: slug}).exclude(pk=instance.pk).exists():
        suffix = f"-{counter}"
        slug = f"{base_slug[: max_length - len(suffix)]}{suffix}"
        counter += 1
    return slug
