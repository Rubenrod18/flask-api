from .base import blueprint as blueprint_base
from .users import blueprint as blueprint_users
from .roles import blueprint as blueprint_roles

blueprints = [
    blueprint_base,
    blueprint_users,
    blueprint_roles,
]
