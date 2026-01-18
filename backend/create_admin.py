"""Script to create initial admin user for production deployment."""

import asyncio
import sys

from sqlalchemy import select

from app.database import get_db_context, init_db
from app.models.user import User
from app.services.auth import get_password_hash


async def create_admin_user():
    """Create admin user if not exists."""
    print("🔧 Initializing database...")

    # Initialize database tables
    await init_db()
    print("✅ Database initialized!")

    # Create admin user
    async with get_db_context() as db:
        # Check if admin exists
        result = await db.execute(
            select(User).where(User.email == "admin@example.com")
        )
        existing_admin = result.scalar_one_or_none()

        if existing_admin:
            print("⚠️  Admin user already exists!")
            print(f"   Email: admin@example.com")
            print(f"   ID: {existing_admin.id}")
            return

        # Create new admin user
        admin = User(
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=get_password_hash("Admin123"),
            is_active=True,
            is_superuser=True,
        )

        db.add(admin)
        await db.commit()
        await db.refresh(admin)

        print("✅ Admin user created successfully!")
        print(f"   Email: admin@example.com")
        print(f"   Password: Admin123")
        print(f"   ID: {admin.id}")
        print("")
        print("⚠️  IMPORTANT: Change the password after first login!")


async def main():
    """Main entry point."""
    try:
        await create_admin_user()
        print("\n🎉 Setup complete! You can now login to the application.")
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
