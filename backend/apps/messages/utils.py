from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_ws_event(user_id: str, event_type: str, data: dict) -> None:
    """Push an event to a user's personal WebSocket channel group."""
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f"user_{user_id}",
            {"type": event_type, "data": data},
        )
