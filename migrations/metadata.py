"""What the migrations describe: every model, minus what tenancy.py adds by hand."""

import app.models  # noqa: F401  (registers every family and catalog table)
import app.models.admin  # noqa: F401
from app.db import AdminBase, CatalogBase, TenantBase
from migrations.tenancy import TENANCY_CONSTRAINT_PREFIXES

target_metadata = [CatalogBase.metadata, AdminBase.metadata, TenantBase.metadata]


def include_object(obj, name, type_, reflected, compare_to):
    """Autogenerate ignores the constraints tenancy.py adds (they aren't in the models)."""
    if type_ in {"foreign_key_constraint", "unique_constraint"} and name:
        return not name.startswith(TENANCY_CONSTRAINT_PREFIXES)
    return True
