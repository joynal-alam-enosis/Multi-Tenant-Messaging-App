from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import F
from django.utils import timezone
from apps.conversations.models import Conversation, ConversationParticipant
from apps.conversations.permissions import IsConversationParticipant
from apps.conversations.cache import invalidate_inbox_cache
from .models import Message
from .serializers import MessageSerializer, MessageCreateSerializer
from .utils import send_ws_event

class MessageListView(APIView):
    permission_classes = [IsAuthenticated, IsConversationParticipant]

    def get_conversation(self, pk):
        from django.shortcuts import get_object_or_404
        conv = get_object_or_404(Conversation, pk=pk)
        self.check_object_permissions(self.request, conv)
        return conv

    def get(self, request, pk):
        conv = self.get_conversation(pk)
        messages = Message.objects.filter(conversation=conv).select_related('sender__tenant').order_by('created_at')
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request, pk):
        conv = self.get_conversation(pk)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            conversation=conv,
            sender=request.user,
            content=serializer.validated_data['content']
        )
        
        # Update last activity
        conv.last_activity_at = message.created_at
        conv.save()
        
        # Update other participant's unread_count
        other_participant = ConversationParticipant.objects.filter(
            conversation=conv
        ).exclude(user=request.user).first()
        
        if other_participant:
            other_participant.unread_count = F('unread_count') + 1
            other_participant.save()
            
            # Invalidate both caches
            invalidate_inbox_cache(str(request.user.id))
            invalidate_inbox_cache(str(other_participant.user.id))

            # Push WS event to receiver
            send_ws_event(
                user_id=str(other_participant.user.id),
                event_type="new_message",
                data={
                    "conversation_id": str(conv.id),
                    "message": MessageSerializer(message).data,
                }
            )
            
        # Push WS event to sender (for multi-device sync)
        send_ws_event(
            user_id=str(request.user.id),
            event_type="new_message",
            data={
                "conversation_id": str(conv.id),
                "message": MessageSerializer(message).data,
            }
        )

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

class MessageReadView(APIView):
    permission_classes = [IsAuthenticated, IsConversationParticipant]

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        conv = get_object_or_404(Conversation, pk=pk)
        self.check_object_permissions(self.request, conv)

        Message.objects.filter(
            conversation=conv
        ).exclude(
            sender=request.user
        ).filter(
            is_read=False
        ).update(is_read=True)

        participant = ConversationParticipant.objects.get(conversation=conv, user=request.user)
        participant.unread_count = 0
        participant.last_read_at = timezone.now()
        participant.save()

        invalidate_inbox_cache(str(request.user.id))

        other_participant = ConversationParticipant.objects.filter(
            conversation=conv
        ).exclude(user=request.user).first()

        if other_participant:
            send_ws_event(
                user_id=str(other_participant.user.id),
                event_type="message_read",
                data={
                    "conversation_id": str(conv.id),
                    "reader_id": str(request.user.id),
                    "read_at": participant.last_read_at.isoformat(),
                }
            )
            
        send_ws_event(
            user_id=str(request.user.id),
            event_type="message_read",
            data={
                "conversation_id": str(conv.id),
                "reader_id": str(request.user.id),
                "read_at": participant.last_read_at.isoformat(),
            }
        )

        return Response({"status": "ok"})
