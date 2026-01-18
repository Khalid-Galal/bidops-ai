"""Role-based permissions."""

from enum import Enum
from typing import Set

from app.models.base import UserRole


class Permission(str, Enum):
    """System permissions."""

    # Project permissions
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    PROJECT_ARCHIVE = "project:archive"

    # Document permissions
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_READ = "document:read"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_REPROCESS = "document:reprocess"

    # Package permissions
    PACKAGE_CREATE = "package:create"
    PACKAGE_UPDATE = "package:update"
    PACKAGE_DELETE = "package:delete"
    PACKAGE_SEND = "package:send"

    # Supplier permissions
    SUPPLIER_CREATE = "supplier:create"
    SUPPLIER_READ = "supplier:read"
    SUPPLIER_UPDATE = "supplier:update"
    SUPPLIER_DELETE = "supplier:delete"
    SUPPLIER_IMPORT = "supplier:import"

    # Offer permissions
    OFFER_UPLOAD = "offer:upload"
    OFFER_READ = "offer:read"
    OFFER_EVALUATE = "offer:evaluate"
    OFFER_SELECT = "offer:select"

    # Pricing permissions
    PRICING_VIEW = "pricing:view"
    PRICING_POPULATE = "pricing:populate"
    PRICING_APPROVE = "pricing:approve"
    PRICING_EXPORT = "pricing:export"

    # Email permissions
    EMAIL_SEND = "email:send"
    EMAIL_VIEW = "email:view"

    # Admin permissions
    ADMIN_USERS = "admin:users"
    ADMIN_SETTINGS = "admin:settings"
    ADMIN_AUDIT = "admin:audit"


# Role to permissions mapping
ROLE_PERMISSIONS: dict[UserRole, Set[Permission]] = {
    UserRole.ADMIN: set(Permission),  # All permissions

    UserRole.TENDER_MANAGER: {
        # Projects
        Permission.PROJECT_CREATE,
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.PROJECT_DELETE,
        Permission.PROJECT_ARCHIVE,
        # Documents
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        Permission.DOCUMENT_DELETE,
        Permission.DOCUMENT_REPROCESS,
        # Packages
        Permission.PACKAGE_CREATE,
        Permission.PACKAGE_UPDATE,
        Permission.PACKAGE_DELETE,
        Permission.PACKAGE_SEND,
        # Suppliers
        Permission.SUPPLIER_CREATE,
        Permission.SUPPLIER_READ,
        Permission.SUPPLIER_UPDATE,
        Permission.SUPPLIER_DELETE,
        Permission.SUPPLIER_IMPORT,
        # Offers
        Permission.OFFER_UPLOAD,
        Permission.OFFER_READ,
        Permission.OFFER_EVALUATE,
        Permission.OFFER_SELECT,
        # Pricing
        Permission.PRICING_VIEW,
        Permission.PRICING_POPULATE,
        Permission.PRICING_APPROVE,
        Permission.PRICING_EXPORT,
        # Email
        Permission.EMAIL_SEND,
        Permission.EMAIL_VIEW,
    },

    UserRole.ESTIMATOR: {
        # Projects
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        # Documents
        Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ,
        # Packages
        Permission.PACKAGE_CREATE,
        Permission.PACKAGE_UPDATE,
        # Suppliers
        Permission.SUPPLIER_READ,
        # Offers
        Permission.OFFER_UPLOAD,
        Permission.OFFER_READ,
        Permission.OFFER_EVALUATE,
        # Pricing
        Permission.PRICING_VIEW,
        Permission.PRICING_POPULATE,
        Permission.PRICING_EXPORT,
        # Email
        Permission.EMAIL_VIEW,
    },

    UserRole.VIEWER: {
        # Read-only access
        Permission.PROJECT_READ,
        Permission.DOCUMENT_READ,
        Permission.SUPPLIER_READ,
        Permission.OFFER_READ,
        Permission.PRICING_VIEW,
        Permission.EMAIL_VIEW,
    },
}


def check_permission(role: UserRole, permission: Permission) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: The user's role
        permission: The permission to check

    Returns:
        True if the role has the permission, False otherwise
    """
    role_perms = ROLE_PERMISSIONS.get(role, set())
    return permission in role_perms


def get_role_permissions(role: UserRole) -> Set[Permission]:
    """Get all permissions for a role.

    Args:
        role: The user's role

    Returns:
        Set of permissions for the role
    """
    return ROLE_PERMISSIONS.get(role, set())
