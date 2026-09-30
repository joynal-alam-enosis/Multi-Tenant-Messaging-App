"""Seed tenants, local users, Cognito identities, conversations, and messages."""
from __future__ import annotations

import os

from django.core.management.base import BaseCommand, CommandError
from botocore.exceptions import BotoCoreError, ClientError
from rest_framework.authtoken.models import Token

from apps.conversations.models import Conversation, ConversationParticipant
from apps.messages.models import Message
from apps.tenants.models import Tenant
from apps.users.cognito import (
    SEED_PASSWORD_DEFAULT,
    ensure_cognito_user,
    ensure_user_pool_and_client,
)
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed the database with test tenants, users, conversations, and messages"

    def handle(self, *args, **options) -> None:
        seed_password = os.environ.get("SEED_PASSWORD", SEED_PASSWORD_DEFAULT)

        try:
            pool_state = ensure_user_pool_and_client()
        except (BotoCoreError, ClientError, OSError, KeyError, TypeError, ValueError) as exc:
            raise CommandError(f"Cognito bootstrap failed during seed: {exc}") from exc

        user_pool_id = pool_state["user_pool_id"]

        acme, _ = Tenant.objects.get_or_create(slug="acme", defaults={"name": "Acme Corp"})
        globex, _ = Tenant.objects.get_or_create(slug="globex", defaults={"name": "Globex Inc"})

        users_data = [
            {"email": "alice@acme.com", "first_name": "Alice", "last_name": "Johnson", "tenant": acme, "username": "alice"},
            {"email": "bob@acme.com", "first_name": "Bob", "last_name": "Williams", "tenant": acme, "username": "bob"},
            {"email": "charlie@acme.com", "first_name": "Charlie", "last_name": "Brown", "tenant": acme, "username": "charlie"},
            {"email": "dave@globex.com", "first_name": "Dave", "last_name": "Smith", "tenant": globex, "username": "dave"},
            {"email": "eve@globex.com", "first_name": "Eve", "last_name": "Davis", "tenant": globex, "username": "eve"},
            {"email": "frank@globex.com", "first_name": "Frank", "last_name": "Miller", "tenant": globex, "username": "frank"},
        ]

        created_users: dict[str, User] = {}
        for u_data in users_data:
            user, _created = User.objects.get_or_create(email=u_data["email"], defaults=u_data)
            user.set_password(seed_password)
            user.save(update_fields=["password"])

            try:
                cognito_sub = ensure_cognito_user(
                    email=user.email,
                    password=seed_password,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    user_pool_id=user_pool_id,
                )
            except (BotoCoreError, ClientError, RuntimeError, OSError, KeyError) as exc:
                raise CommandError(f"Failed to seed Cognito user {user.email}: {exc}") from exc

            if user.cognito_sub != cognito_sub:
                user.cognito_sub = cognito_sub
                user.save(update_fields=["cognito_sub"])

            Token.objects.get_or_create(user=user)
            created_users[u_data["username"]] = user

        def create_conv(user_one: User, user_two: User) -> Conversation:
            existing = (
                Conversation.objects.filter(participants__user=user_one)
                .filter(participants__user=user_two)
                .first()
            )
            if existing:
                return existing
            conv = Conversation.objects.create()
            ConversationParticipant.objects.create(conversation=conv, user=user_one)
            ConversationParticipant.objects.create(conversation=conv, user=user_two)
            return conv

        alice = created_users["alice"]
        bob = created_users["bob"]
        dave = created_users["dave"]
        eve = created_users["eve"]

        conversation_alice_bob = create_conv(alice, bob)
        if not conversation_alice_bob.messages.exists():
            Message.objects.create(conversation=conversation_alice_bob, sender=alice, content="Hi Bob!")
            Message.objects.create(conversation=conversation_alice_bob, sender=bob, content="Hello Alice!")

        conversation_alice_dave = create_conv(alice, dave)
        if not conversation_alice_dave.messages.exists():
            Message.objects.create(
                conversation=conversation_alice_dave,
                sender=alice,
                content="Hi Dave, from Acme!",
            )
            Message.objects.create(
                conversation=conversation_alice_dave,
                sender=dave,
                content="Hello Alice, nice to meet you.",
            )

        conversation_bob_eve = create_conv(bob, eve)
        if not conversation_bob_eve.messages.exists():
            Message.objects.create(
                conversation=conversation_bob_eve,
                sender=eve,
                content="Hi Bob, do you have those files?",
            )

        self.stdout.write(self.style.SUCCESS("Seed data created successfully!"))
        self.stdout.write(f"Cognito pool: {user_pool_id}  client: {pool_state['client_id']}")
        self.stdout.write(f"Demo password (Cognito + Django): {seed_password}")
        self.stdout.write("Test users:")
        for user in User.objects.select_related("tenant").all():
            token = Token.objects.get(user=user)
            self.stdout.write(
                f"- {user.email}  tenant={user.tenant.slug}  "
                f"cognito_sub={user.cognito_sub}  drf_token={token.key}"
            )
