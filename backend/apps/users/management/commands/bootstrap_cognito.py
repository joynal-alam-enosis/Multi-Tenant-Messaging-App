"""
Ensure a Cognito User Pool + app client exist (MiniStack locally, AWS in prod).

Idempotent: reuses pool/client by name and writes IDs to cognito_state.json.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from botocore.exceptions import BotoCoreError, ClientError

from apps.users.cognito import cognito_state_path, ensure_user_pool_and_client


class Command(BaseCommand):
    help = "Bootstrap Cognito User Pool and app client (idempotent)"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--pool-name",
            default=None,
            help="User pool name (default: COGNITO_POOL_NAME / messaging-app)",
        )
        parser.add_argument(
            "--client-name",
            default=None,
            help="App client name (default: COGNITO_CLIENT_NAME / messaging-web)",
        )

    def handle(self, *args, **options) -> None:
        try:
            state = ensure_user_pool_and_client(
                pool_name=options.get("pool_name"),
                client_name=options.get("client_name"),
            )
        except (BotoCoreError, ClientError, OSError, KeyError, TypeError, ValueError) as exc:
            raise CommandError(f"Cognito bootstrap failed: {exc}") from exc

        path = cognito_state_path()
        pool_note = "created" if state.get("created_pool") else "reused"
        client_note = "created" if state.get("created_client") else "reused"

        self.stdout.write(self.style.SUCCESS("Cognito bootstrap OK"))
        self.stdout.write(f"  Pool   ({pool_note}): {state['user_pool_id']}  name={state['pool_name']}")
        self.stdout.write(f"  Client ({client_note}): {state['client_id']}  name={state['client_name']}")
        self.stdout.write(f"  Region: {state['region']}")
        self.stdout.write(f"  Endpoint: {state['endpoint'] or '(AWS default)'}")
        self.stdout.write(f"  State file: {path}")
        self.stdout.write("")
        self.stdout.write("Export for host / frontend (optional):")
        self.stdout.write(f"  COGNITO_USER_POOL_ID={state['user_pool_id']}")
        self.stdout.write(f"  COGNITO_CLIENT_ID={state['client_id']}")
