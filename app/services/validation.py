def require_fields(values: dict[str, str], required: dict[str, str]) -> dict[str, str]:
    """Check that each key in `required` is non-blank in `values`.

    `required` maps field name -> error message to show when blank/missing.
    Returns a dict of field name -> error message for every field that failed.
    """
    errors = {}
    for field, message in required.items():
        if not (values.get(field) or "").strip():
            errors[field] = message
    return errors
