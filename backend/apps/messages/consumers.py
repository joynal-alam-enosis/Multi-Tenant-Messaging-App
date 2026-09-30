import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")
        
        if not self.user or self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f"user_{self.user.id}"
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    # Event handlers
    async def new_message(self, event):
        await self.send_json(event)

    async def message_read(self, event):
        await self.send_json(event)

    async def conversation_updated(self, event):
        await self.send_json(event)
