import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import { User } from '../types';

export const UserSearch = ({ onConversationCreated }: { onConversationCreated: (id: string) => void }) => {
  const [query, setQuery] = useState('');
  const queryClient = useQueryClient();

  const { data: users = [], isLoading } = useQuery<User[]>({
    queryKey: ['users', 'search', query],
    queryFn: async () => {
      const res = await apiClient.get('/users/search/', { params: { q: query } });
      return res.data;
    },
    enabled: query.length > 0
  });

  const createConversation = useMutation({
    mutationFn: async (userId: string) => apiClient.post('/conversations/', { user_id: userId }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
      onConversationCreated(res.data.id);
      setQuery('');
    }
  });

  return (
    <div className="p-4 border-b">
      <h3 className="text-sm font-medium text-gray-700 mb-2">New Conversation</h3>
      <input
        type="text"
        placeholder="Find users..."
        className="w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 mb-2"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      {isLoading && <div className="text-xs text-gray-500">Searching...</div>}
      {users.length > 0 && (
        <ul className="mt-2 border rounded divide-y max-h-40 overflow-y-auto bg-white shadow-sm absolute w-1/3 z-10">
          {users.map(u => (
            <li
              key={u.id}
              onClick={() => createConversation.mutate(u.id)}
              className="p-2 hover:bg-gray-50 cursor-pointer flex flex-col"
            >
              <span className="font-medium text-sm">{u.first_name} {u.last_name}</span>
              <span className="text-xs text-gray-500">{u.email} • {u.tenant_name}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
