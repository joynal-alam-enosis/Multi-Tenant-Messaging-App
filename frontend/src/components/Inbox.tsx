import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { Conversation } from '../types';

export const Inbox = ({ onSelect, selectedId }: { onSelect: (id: string) => void, selectedId: string | null }) => {
  const [filter, setFilter] = useState<'all' | 'unread' | 'starred'>('all');
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();

  const { data: conversations = [], isLoading } = useQuery<Conversation[]>({
    queryKey: ['conversations', filter, search],
    queryFn: async () => {
      const res = await apiClient.get('/conversations/', { params: { filter, search } });
      return res.data;
    }
  });

  const toggleStar = useMutation({
    mutationFn: async (id: string) => apiClient.patch(`/conversations/${id}/star/`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['conversations'] })
  });

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b">
        <input
          type="text"
          placeholder="Search inbox..."
          className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="flex gap-2 mt-3 text-sm">
          {(['all', 'unread', 'starred'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1 rounded-full capitalize ${filter === f ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="p-4 text-center text-gray-500">Loading...</div>
        ) : conversations.length === 0 ? (
          <div className="p-4 text-center text-gray-500">No conversations found.</div>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              className={`p-4 border-b cursor-pointer hover:bg-gray-50 ${selectedId === conv.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''}`}
            >
              <div className="flex justify-between items-start mb-1">
                <span className={`font-medium ${conv.unread_count > 0 ? 'text-black' : 'text-gray-700'}`}>
                  {conv.other_participant.first_name} {conv.other_participant.last_name}
                </span>
                <button
                  onClick={(e) => { e.stopPropagation(); toggleStar.mutate(conv.id); }}
                  className={`text-lg ${conv.is_starred ? 'text-yellow-400' : 'text-gray-300 hover:text-gray-400'}`}
                >
                  ★
                </button>
              </div>
              <div className="text-xs text-gray-500 mb-1">{conv.other_participant.tenant_name}</div>
              <div className="flex justify-between items-center">
                <span className={`text-sm truncate pr-4 ${conv.unread_count > 0 ? 'font-medium text-gray-800' : 'text-gray-500'}`}>
                  {conv.last_message || 'No messages yet'}
                </span>
                {conv.unread_count > 0 && (
                  <span className="bg-blue-600 text-white text-xs px-2 py-0.5 rounded-full min-w-[1.25rem] text-center">
                    {conv.unread_count}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
