# Import all models so Alembic (and other tools) can detect them.
from app.db.models.b2b_account import B2BAccount  # noqa: F401
from app.db.models.group import Group  # noqa: F401
from app.db.models.user import User  # noqa: F401
from app.db.models.card import Card  # noqa: F401
from app.db.models.code_3ds import Code3ds  # noqa: F401
