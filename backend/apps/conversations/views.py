from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch, Q
from .models import Conversation, ConversationParticipant
from .serializers import ConversationListSerializer, ConversationCreateSerializer
from .permissions import IsConversationParticipant
from .cache import get_cached_inbox, set_inbox_cache, invalidate_inbox_cache
from apps.users.models import User

class ConversationViewSet(viewsets.ModelViewSet):
    serializer_class = ConversationListSerializer
    
    def get_permissions(self):
        if self.action in ['retrieve', 'star']:
            return [IsAuthenticated(), IsConversationParticipant()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.filter(
            participants__user=user
        ).prefetch_related(
            Prefetch('participants', queryset=ConversationParticipant.objects.select_related('user__tenant'))
        ).distinct()
        return queryset

    def list(self, request, *args, **kwargs):
        user = request.user
        filter_type = request.query_params.get('filter', 'all')
        search_query = request.query_params.get('search', '')

        if not search_query:
            cached_data = get_cached_inbox(str(user.id), filter_type)
            if cached_data is not None:
                return Response(cached_data)

        queryset = self.get_queryset()

        if filter_type == 'unread':
            queryset = queryset.filter(participants__user=user, participants__unread_count__gt=0)
        elif filter_type == 'starred':
            queryset = queryset.filter(participants__user=user, participants__is_starred=True)

        if search_query:
            queryset = queryset.filter(
                Q(messages__content__icontains=search_query) |
                (Q(participants__user__first_name__icontains=search_query) & ~Q(participants__user=user)) |
                (Q(participants__user__last_name__icontains=search_query) & ~Q(participants__user=user))
            )

        queryset = queryset.order_by('-last_activity_at')

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        if not search_query:
            set_inbox_cache(str(user.id), filter_type, data)

        return Response(data)

    def create(self, request, *args, **kwargs):
        serializer = ConversationCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        target_user_id = serializer.validated_data['user_id']
        target_user = User.objects.get(id=target_user_id)
        
        existing = Conversation.objects.filter(
            participants__user=request.user
        ).filter(
            participants__user=target_user
        ).first()

        if existing:
            out_serializer = self.get_serializer(existing)
            return Response(out_serializer.data, status=status.HTTP_200_OK)

        conv = Conversation.objects.create()
        ConversationParticipant.objects.create(conversation=conv, user=request.user)
        ConversationParticipant.objects.create(conversation=conv, user=target_user)

        invalidate_inbox_cache(str(request.user.id))
        invalidate_inbox_cache(str(target_user.id))

        out_serializer = self.get_serializer(conv)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'])
    def star(self, request, pk=None):
        conversation = self.get_object()
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        participant.is_starred = not participant.is_starred
        participant.save()
        
        invalidate_inbox_cache(str(request.user.id))
        
        return Response({'is_starred': participant.is_starred})
