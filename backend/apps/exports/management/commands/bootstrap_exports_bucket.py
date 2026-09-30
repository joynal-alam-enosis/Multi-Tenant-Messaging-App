"""
Ensure S3 exports bucket exists (MiniStack locally, AWS S3 in production).

Idempotent: creates bucket if it doesn't exist.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from botocore.exceptions import BotoCoreError, ClientError

from apps.exports.s3 import ensure_bucket_exists


class Command(BaseCommand):
    help = "Ensure S3 exports bucket exists (idempotent)"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--bucket-name",
            default=None,
            help="Override bucket name (default: EXPORT_S3_BUCKET setting)",
        )

    def handle(self, *args, **options) -> None:
        try:
            bucket = ensure_bucket_exists(options.get("bucket_name"))
        except (BotoCoreError, ClientError, OSError, KeyError, TypeError, ValueError) as exc:
            raise CommandError(f"S3 bucket bootstrap failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Export bucket ready: {bucket}"))