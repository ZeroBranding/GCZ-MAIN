import argparse
import datetime
import json
import os
import shutil
from pathlib import Path

# --- Configuration ---
# In a real application, this might come from a config file.
# For simplicity, we define it here.
# Quotas are in Megabytes (MB).
ROLE_QUOTAS = {
    "guest": 100,    # 100 MB
    "editor": 1024,  # 1 GB
    "admin": 10240,  # 10 GB
}

DEFAULT_TTL_DAYS = 30
ARTIFACTS_BASE_DIR = Path.cwd() / "artifacts"

# --- Helper Functions ---
def get_dir_size(path: Path) -> float:
    """Calculates the total size of a directory in MB."""
    total_size = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)
    return total_size / (1024 * 1024)

def parse_args():
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(description="Clean up old and oversized artifacts.")
    parser.add_argument(
        "--ttl-days",
        type=int,
        default=DEFAULT_TTL_DAYS,
        help=f"Time-to-live in days. Artifacts older than this will be deleted. Default: {DEFAULT_TTL_DAYS}",
    )
    parser.add_argument(
        "--apply-quotas",
        action="store_true",
        help="Apply user role quotas. This requires run reports with user metadata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate the cleanup without actually deleting any files. Highly recommended for the first run.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging."
    )
    return parser.parse_args()

def get_user_from_run(run_id: str) -> dict:
    """
    Finds the report for a given run ID and extracts user information.
    This is a mock-up function. In a real system, you might query a database.
    """
    report_path = Path.cwd() / "data" / "graph" / "reports" / f"{run_id}.json"
    if report_path.exists():
        try:
            with open(report_path, "r") as f:
                report = json.load(f)
            user_context = report.get("user_context", {})
            return {
                "user_id": user_context.get("user_id", "unknown_user"),
                "role": user_context.get("user_role", "guest"),
            }
        except (json.JSONDecodeError, KeyError):
            pass
    return {"user_id": "unknown_user", "role": "guest"}

def main():
    """Main execution function."""
    args = parse_args()
    print(f"--- Artifact Cleanup ---")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'DELETION'}")
    print(f"Artifacts directory: {ARTIFACTS_BASE_DIR}")
    print("-" * 25)

    if not ARTIFACTS_BASE_DIR.exists():
        print(f"Artifacts directory '{ARTIFACTS_BASE_DIR}' not found. Nothing to do.")
        return

    # --- Time-based Cleanup (TTL) ---
    print(f"\n[1] Performing TTL cleanup (older than {args.ttl_days} days)...")
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=args.ttl_days)
    ttl_deleted_count = 0
    ttl_deleted_size = 0.0

    for run_dir in ARTIFACTS_BASE_DIR.iterdir():
        if not run_dir.is_dir():
            continue
        try:
            dir_stat = run_dir.stat()
            dir_mtime = datetime.datetime.fromtimestamp(dir_stat.st_mtime)
            if dir_mtime < cutoff_date:
                dir_size = get_dir_size(run_dir)
                ttl_deleted_count += 1
                ttl_deleted_size += dir_size
                print(f"  - Deleting '{run_dir.name}' (Reason: TTL, Size: {dir_size:.2f} MB)")
                if not args.dry_run:
                    shutil.rmtree(run_dir)
        except FileNotFoundError:
            # Can happen if a directory is deleted by another process
            continue

    print(f"TTL Cleanup Summary: {ttl_deleted_count} run directories marked for deletion (Total size: {ttl_deleted_size:.2f} MB).")

    # --- Quota-based Cleanup ---
    if args.apply_quotas:
        print(f"\n[2] Performing Quota-based cleanup...")
        user_artifact_sizes = {}

        # First, calculate current usage for all users
        for run_dir in ARTIFACTS_BASE_DIR.iterdir():
            if not run_dir.is_dir():
                continue

            user_info = get_user_from_run(run_dir.name)
            user_id = user_info["user_id"]

            if user_id not in user_artifact_sizes:
                user_artifact_sizes[user_id] = {"size": 0, "role": user_info["role"], "runs": []}

            dir_size = get_dir_size(run_dir)
            user_artifact_sizes[user_id]["size"] += dir_size
            user_artifact_sizes[user_id]["runs"].append((run_dir, dir_mtime))

        # Then, check quotas and delete oldest runs if exceeded
        quota_deleted_count = 0
        quota_deleted_size = 0.0
        for user_id, data in user_artifact_sizes.items():
            role = data["role"]
            quota = ROLE_QUOTAS.get(role, ROLE_QUOTAS["guest"])
            if data["size"] > quota:
                print(f"  - User '{user_id}' (Role: {role}) has exceeded quota ({data['size']:.2f} MB > {quota} MB).")

                # Sort runs by modification time (oldest first)
                sorted_runs = sorted(data["runs"], key=lambda x: x[1])

                size_to_delete = data["size"] - quota
                for run_dir, _ in sorted_runs:
                    if size_to_delete <= 0:
                        break

                    dir_size = get_dir_size(run_dir)
                    print(f"    - Deleting '{run_dir.name}' (Reason: Quota, Size: {dir_size:.2f} MB)")
                    quota_deleted_count += 1
                    quota_deleted_size += dir_size
                    size_to_delete -= dir_size

                    if not args.dry_run:
                        shutil.rmtree(run_dir)

        print(f"Quota Cleanup Summary: {quota_deleted_count} run directories marked for deletion (Total size: {quota_deleted_size:.2f} MB).")

    print("\n--- Cleanup Finished ---")

if __name__ == "__main__":
    main()
