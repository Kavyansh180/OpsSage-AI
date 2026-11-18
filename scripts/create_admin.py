"""
Secure CLI Administrator Provisioning Script for OpsSage AI.
This script provisions the initial administrative user directly into MongoDB Atlas.
It is an operational CLI utility and is NEVER exposed over HTTP.

Usage (Interactive):
    .venv\\Scripts\\python.exe scripts/create_admin.py

Usage (Non-interactive / CI / Automation):
    .venv\\Scripts\\python.exe scripts/create_admin.py --email admin@company.com --name "Ops Admin" --password "SecureAdminPass123!"
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings
from backend.app.core.exceptions import AppException
from backend.app.core.logging import get_logger, setup_logging
from backend.app.db.mongodb import MongoDBManager, _mask_uri
from backend.app.models.user import UserRole
from backend.app.services.auth_service import AuthService

logger = get_logger("scripts.create_admin")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpsSage AI - CLI Administrator Provisioning")
    parser.add_argument("--email", type=str, help="Administrator email address")
    parser.add_argument("--name", type=str, help="Full name of administrator")
    parser.add_argument("--password", type=str, help="Administrator password (hidden prompt if omitted)")
    return parser.parse_args()


async def provision_admin() -> int:
    setup_logging()
    settings = get_settings()
    args = parse_arguments()

    print("==================================================")
    print("   OpsSage AI - Administrator Provisioning CLI   ")
    print("==================================================")
    print(f"Target Database: {settings.MONGODB_DB_NAME}")
    print(f"Connecting to:   {_mask_uri(settings.MONGODB_URI)}")

    # 1. Gather Email
    email = args.email
    if not email:
        email = input("Enter admin email: ").strip()
    if "@" not in email or "." not in email:
        logger.error("[FAILED] Invalid email address format.")
        return 1

    # 2. Gather Name
    name = args.name
    if not name:
        name = input("Enter admin full name: ").strip()
    if len(name) < 2:
        logger.error("[FAILED] Full name must be at least 2 characters.")
        return 1

    # 3. Gather Password securely
    password = args.password
    if not password:
        password = getpass.getpass("Enter secure admin password (min 8 chars): ")
        confirm_pass = getpass.getpass("Confirm admin password: ")
        if password != confirm_pass:
            logger.error("[FAILED] Passwords do not match.")
            return 1

    # 4. Validate UTF-8 byte length (bcrypt 72-byte limit)
    pw_bytes = password.encode("utf-8")
    if len(pw_bytes) < 8:
        logger.error("[FAILED] Password must be at least 8 bytes.")
        return 1
    if len(pw_bytes) > 72:
        logger.error(
            f"[FAILED] Password exceeds bcrypt limit of 72 bytes ({len(pw_bytes)} UTF-8 bytes received). "
            "Please use a shorter password."
        )
        return 1

    # 5. Connect and Provision
    await MongoDBManager.connect()
    if not await MongoDBManager.ping():
        logger.error("[FAILED] Could not connect to MongoDB Atlas. Check your .env configuration.")
        await MongoDBManager.close()
        return 1

    db = MongoDBManager.get_database()
    try:
        admin_user = await AuthService.create_user_with_role(
            db=db,
            email=email,
            password=password,
            full_name=name,
            role=UserRole.ADMIN
        )
        print("--------------------------------------------------")
        print("[SUCCESS] Administrator account provisioned successfully!")
        print(f"  ID:    {admin_user.id}")
        print(f"  Email: {admin_user.email}")
        print(f"  Name:  {admin_user.full_name}")
        print(f"  Role:  {admin_user.role.value}")
        print("--------------------------------------------------")
    except AppException as exc:
        logger.error(f"[FAILED] Provisioning aborted: {exc.message}")
        await MongoDBManager.close()
        return 1
    except Exception as exc:
        logger.error(f"[FAILED] Unexpected error provisioning admin: {exc}")
        await MongoDBManager.close()
        return 1

    await MongoDBManager.close()
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(provision_admin())
    sys.exit(exit_code)
