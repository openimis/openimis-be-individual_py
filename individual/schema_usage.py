"""
The schemas built from fields of the system-wide individual schema.

A module whose model stores such a schema (a benefit plan's beneficiary schema, for
instance) registers it from its `ready()`, so this module can refuse to remove or retype
a field in use, and list the schemas that drifted, without importing that module.
"""

_owners = []


def register_schema_owner(model, code_field, schema_field):
    """`model.<schema_field>` is built from the individual schema; `code_field` names the row."""
    owner = (model, code_field, schema_field)
    if owner not in _owners:
        _owners.append(owner)


def owned_schemas():
    """
    `(model, code, schema)` for every stored schema. Soft-deleted rows count: undoing their
    deletion must not bring back a field the individual schema no longer has.
    """
    from individual.validation import schema_dict

    for model, code_field, schema_field in _owners:
        rows = model.objects.filter(**{f'{schema_field}__isnull': False}) \
            .order_by(code_field).values_list(code_field, schema_field)
        for code, value in rows:
            schema = schema_dict(value)
            if schema is not None:
                yield model, code, schema


def schema_usages(field_names):
    """`(owner code, field name)` for each stored schema using one of `field_names`."""
    field_names = set(field_names)
    if not field_names:
        return []
    return [
        (code, name)
        for _, code, schema in owned_schemas()
        for name in schema.get('properties') or {} if name in field_names
    ]
