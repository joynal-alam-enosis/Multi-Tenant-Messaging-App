import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { Message } from '../types';
import { useAuth } from '../contexts/AuthContext';

export const ConversationView = ({ conversationId }: { conversationId: string }) => {
  const { user } = useAuth();
  const [content, setContent] = useState('');
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: messages = [], isLoading } = useQuery<Message[]>({
    queryKey: ['messages', conversationId],
    queryFn: async () => {
      const res = await apiClient.get(`/conversations/${conversationId}/messages/`);
      return res.data;
    },
    enabled: !!conversationId
  });

  const markRead = useMutation({
    mutationFn: async () => apiClient.post(`/conversations/${conversationId}/messages/read/`),
    onSuccess: () => {
      queryClient.setQueryData(['messages', conversationId], (old: Message[] | undefined) => {
        if (!old) return old;
        return old.map(m => (m.sender.id !== user?.id && !m.is_read) ? { ...m, is_read: true } : m);
      });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    }
  });

  const sendMessage = useMutation({
    mutationFn: async (text: string) => apiClient.post(`/conversations/${conversationId}/messages/`, { content: text }),
    onSuccess: (res) => {
      queryClient.setQueryData(['messages', conversationId], (old: Message[] | undefined) => {
        if (!old) return [res.data];
        if (old.some(m => m.id === res.data.id)) return old;
        return [...old, res.data];
      });
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    }
  });

  useEffect(() => {
    if (messages.some(m => m.sender.id !== user?.id && !m.is_read)) {
      markRead.mutate();
    }
    // Scroll to bottom
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, user?.id]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;
    sendMessage.mutate(content);
    setContent('');
  };

  const [exportTaskId, setExportTaskId] = useState<string | null>(null);
  
  const { data: exportTask } = useQuery({
    queryKey: ['export', exportTaskId],
    queryFn: async () => {
      if (!exportTaskId) return null;
      const res = await apiClient.get(`/exports/${exportTaskId}/`);
      return res.data;
    },
    enabled: !!exportTaskId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && (data.status === 'completed' || data.status === 'failed')) return false;
      return 2000;
    }
  });

  if (isLoading) return <div className="flex-1 flex items-center justify-center">Loading...</div>;

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b bg-gray-50 flex justify-between items-center">
        <h3 className="font-medium">Conversation</h3>
        <div className="flex items-center gap-2">
          {exportTask?.status === 'pending' || exportTask?.status === 'processing' ? (
            <span className="text-xs text-blue-600">Exporting...</span>
          ) : exportTask?.status === 'completed' ? (
            <button
              onClick={async () => {
                const res = await apiClient.get(`/exports/${exportTaskId}/download/`, { responseType: 'blob' });
                const url = window.URL.createObjectURL(new Blob([res.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `conversation_export_${exportTaskId}.json`);
                document.body.appendChild(link);
                link.click();
                link.remove();
              }}
              className="text-xs px-3 py-1 bg-green-50 text-green-700 border border-green-200 rounded hover:bg-green-100"
            >
              Download Export
            </button>
          ) : (
            <button
              onClick={async () => {
                const res = await apiClient.post(`/conversations/${conversationId}/export/`);
                setExportTaskId(res.data.id);
              }}
              className="text-xs px-3 py-1 bg-white border rounded hover:bg-gray-100"
            >
              Request Export
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
        {messages.map(msg => {
          const isMine = msg.sender.id === user?.id;
          return (
            <div key={msg.id} className={`flex flex-col ${isMine ? 'items-end' : 'items-start'}`}>
              <div className="text-xs text-gray-500 mb-1">
                {!isMine && <span className="font-medium mr-2">{msg.sender.first_name}</span>}
                {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div className={`px-4 py-2 rounded-2xl max-w-[75%] ${isMine ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-200 text-gray-900 rounded-bl-none'}`}>
                {msg.content}
              </div>
              {isMine && (
                <div className="text-[10px] text-gray-400 mt-1">
                  {msg.is_read ? 'Read' : 'Delivered'}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="p-4 bg-white border-t">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            placeholder="Type a message..."
            className="flex-1 px-4 py-2 border rounded-full focus:outline-none focus:ring-1 focus:ring-blue-500"
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <button
            type="submit"
            disabled={!content.trim() || sendMessage.isPending}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
};
