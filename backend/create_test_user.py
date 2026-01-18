"""Create test user for development."""
import asyncio
from sqlalchemy import select
from app.database import get_db_context
from app.models.user import User, Organization
from app.models.base import UserRole
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_data():
    """Create test organization and user."""
    async with get_db_context() as session:
        # Check if organization already exists
        result = await session.execute(
            select(Organization).where(Organization.code == "TEST")
        )
        org = result.scalar_one_or_none()

        if not org:
            # Create test organization
            org = Organization(
                name="Test Organization",
                code="TEST",
                description="Test organization for development",
                email="test@bidops.test",
                is_active=True
            )
            session.add(org)
            await session.flush()
            print(f"[OK] Created organization: {org.name} (ID: {org.id})")
        else:
            print(f"[OK] Organization already exists: {org.name} (ID: {org.id})")

        # Check if test user already exists
        result = await session.execute(
            select(User).where(User.email == "admin@bidops.test")
        )
        user = result.scalar_one_or_none()

        if not user:
            # Create test user
            user = User(
                email="admin@bidops.test",
                hashed_password=pwd_context.hash("Admin@123"),
                full_name="Admin User",
                role=UserRole.ADMIN,
                organization_id=org.id,
                is_active=True,
                is_verified=True
            )
            session.add(user)
            await session.commit()
            print(f"[OK] Created admin user: {user.email}")
            print(f"     Password: Admin@123")
        else:
            print(f"[OK] Admin user already exists: {user.email}")

        print("\n=== Test data setup complete! ===")
        print(f"Email: admin@bidops.test")
        print(f"Password: Admin@123")
        print(f"Organization: {org.name}")

if __name__ == "__main__":
    asyncio.run(create_test_data())
