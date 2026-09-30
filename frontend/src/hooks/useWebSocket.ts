import { useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { wsManager } from '../utils/websocket';
import { useQueryClient } from '@tanstack/react-query';
import { Message } from '../types';

export const useWebSocket = () => {
  const { token } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (token) {
      wsManager.connect(token);
    } else {
      wsManager.disconnect();
    }
    return () => wsManager.disconnect();
  }, [token]);

  useEffect(() => {
    const handleNewMessage = (data: { conversation_id: string; message: Message }) => {
      // 1. Update messages list if it's currently fetched
      queryClient.setQueryData(
        ['messages', data.conversation_id],
        (oldMessages: Message[] | undefined) => {
          if (!oldMessages) return oldMessages;
          // Deduplicate
          if (oldMessages.some(m => m.id === data.message.id)) return oldMessages;
          return [...oldMessages, data.message];
        }
      );
      // 2. Invalidate inbox to refresh latest message and unread count
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    };

    const handleMessageRead = (data: { conversation_id: string; reader_id: string; read_at: string }) => {
      queryClient.setQueryData(
        ['messages', data.conversation_id],
        (oldMessages: Message[] | undefined) => {
          if (!oldMessages) return oldMessages;
          return oldMessages.map(msg => 
            msg.sender.id !== data.reader_id ? { ...msg, is_read: true } : msg
          );
        }
      );
    };

    wsManager.subscribe('new_message', handleNewMessage);
    wsManager.subscribe('message_read', handleMessageRead);

    return () => {
      wsManager.unsubscribe('new_message', handleNewMessage);
      wsManager.unsubscribe('message_read', handleMessageRead);
    };
  }, [queryClient]);
};
