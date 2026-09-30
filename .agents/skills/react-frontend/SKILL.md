---
name: react-frontend-development
description: >-
  Use this skill when building or modifying the React frontend — components, hooks,
  API client, WebSocket integration, routing, or styling for the messaging application.
---

# React Frontend Development Skill

## Technology Stack
- React 18.x
- TypeScript 5.x (strict mode)
- Vite (build tool)
- React Router 6.x
- TanStack Query (React Query) v5
- Axios (HTTP client)
- Tailwind CSS 3.x
- Native WebSocket API

## Project Layout

```
frontend/
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   │
│   ├── api/                      # API client layer (Axios)
│   │   ├── client.ts             # Axios instance + interceptors
│   │   ├── conversations.ts
│   │   ├── messages.ts
│   │   ├── users.ts
│   │   └── exports.ts
│   │
│   ├── hooks/                    # Custom React hooks
│   │   ├── useConversations.ts
│   │   ├── useMessages.ts
│   │   ├── useUserSearch.ts
│   │   ├── useWebSocket.ts
│   │   └── useExport.ts
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx
│   │   │   └── Header.tsx
│   │   ├── inbox/
│   │   │   ├── InboxView.tsx
│   │   │   ├── ConversationItem.tsx
│   │   │   ├── InboxFilters.tsx
│   │   │   └── InboxSearch.tsx
│   │   ├── conversation/
│   │   │   ├── ConversationView.tsx
│   │   │   ├── MessageBubble.tsx
│   │   │   ├── MessageComposer.tsx
│   │   │   ├── MessageList.tsx
│   │   │   └── EmptyState.tsx
│   │   ├── users/
│   │   │   ├── UserSearch.tsx
│   │   │   └── UserResult.tsx
│   │   └── common/
│   │       ├── LoadingSpinner.tsx
│   │       ├── ErrorState.tsx
│   │       ├── UnreadBadge.tsx
│   │       └── StarIcon.tsx
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── InboxPage.tsx
│   │   └── ConversationPage.tsx
│   │
│   ├── contexts/
│   │   └── AuthContext.tsx
│   │
│   ├── types/
│   │   └── index.ts
│   │
│   └── utils/
│       ├── formatTime.ts
│       └── websocket.ts
│
├── index.html
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
├── package.json
└── Dockerfile
```

## TypeScript Types

Always define these interfaces in `src/types/index.ts`:

```typescript
export interface Tenant {
  id: string;
  name: string;
  slug: string;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  tenant: Tenant;
}

export interface Conversation {
  id: string;
  participants: User[];
  last_message: string | null;
  last_activity_at: string;
  created_at: string;
  is_starred: boolean;
  unread_count: number;
}

export interface Message {
  id: string;
  conversation_id: string;
  sender: User;
  content: string;
  is_read: boolean;
  created_at: string;
}

export interface ExportTask {
  id: string;
  conversation_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  completed_at: string | null;
}

// WebSocket event types
export type WSEventType = 'new_message' | 'message_read' | 'conversation_updated';

export interface WSEvent {
  type: WSEventType;
  data: Record<string, unknown>;
}
```

## API Client Pattern

```typescript
// src/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
});

// Add auth token to every request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

export default apiClient;
```

## TanStack Query Patterns

### Inbox Hook
```typescript
export function useConversations(filter: 'all' | 'unread' | 'starred', search?: string) {
  return useQuery({
    queryKey: ['conversations', filter, search],
    queryFn: () => fetchConversations({ filter, search }),
    staleTime: 30_000, // matches backend cache TTL
  });
}
```

### Messages Hook
```typescript
export function useMessages(conversationId: string) {
  return useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => fetchMessages(conversationId),
    enabled: !!conversationId,
  });
}
```

### Send Message Mutation
```typescript
export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => sendMessage(conversationId, content),
    onSuccess: (newMessage) => {
      // Optimistically add the message
      queryClient.setQueryData<Message[]>(
        ['messages', conversationId],
        (old = []) => [...old, newMessage]
      );
      queryClient.invalidateQueries({ queryKey: ['conversations'] });
    },
  });
}
```

## WebSocket Integration Pattern

```typescript
// src/hooks/useWebSocket.ts
export function useWebSocket() {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  
  useEffect(() => {
    if (!user) return;
    const token = localStorage.getItem('auth_token');
    const ws = new WebSocket(`ws://localhost:8000/ws/chat/?token=${token}`);
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'new_message':
          // Deduplicate: only add if message ID doesn't exist
          queryClient.setQueryData<Message[]>(
            ['messages', data.data.conversation_id],
            (old = []) => {
              if (old.some(m => m.id === data.data.message.id)) return old;
              return [...old, data.data.message];
            }
          );
          queryClient.invalidateQueries({ queryKey: ['conversations'] });
          break;
        case 'message_read':
          queryClient.invalidateQueries({
            queryKey: ['messages', data.data.conversation_id]
          });
          break;
        case 'conversation_updated':
          queryClient.invalidateQueries({ queryKey: ['conversations'] });
          break;
      }
    };
    
    return () => ws.close();
  }, [user, queryClient]);
}
```

## Component Conventions

### Every data-fetching component MUST handle 3 states:
```tsx
function ConversationView({ id }: { id: string }) {
  const { data, isLoading, error } = useMessages(id);
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorState message="Failed to load messages" />;
  if (!data?.length) return <EmptyState message="No messages yet. Say hello!" />;
  
  return <MessageList messages={data} />;
}
```

### Star icon — toggle only the current user's star state:
```tsx
function StarButton({ conversationId, isStarred }: Props) {
  const mutation = useStarConversation();
  return (
    <button onClick={() => mutation.mutate({ conversationId, starred: !isStarred })}>
      {isStarred ? <StarFilledIcon /> : <StarOutlineIcon />}
    </button>
  );
}
```

### Show tenant name in all user displays:
```tsx
function UserInfo({ user }: { user: User }) {
  return (
    <div>
      <span className="font-medium">{user.first_name} {user.last_name}</span>
      <span className="text-gray-500 text-sm ml-1">({user.tenant.name})</span>
    </div>
  );
}
```

## Routing Structure

```tsx
<Routes>
  <Route path="/login" element={<LoginPage />} />
  <Route element={<ProtectedRoute />}>
    <Route element={<AppLayout />}>
      <Route path="/" element={<InboxPage />} />
      <Route path="/conversations/:id" element={<ConversationPage />} />
    </Route>
  </Route>
</Routes>
```

## Styling Rules (Tailwind)
- Use Tailwind utility classes — no custom CSS files unless absolutely necessary.
- Consistent color scheme: use `indigo` for primary actions, `gray` for secondary.
- Unread badge: `bg-red-500 text-white rounded-full text-xs px-2`.
- Star icon: `text-yellow-400` when starred, `text-gray-300` when not.
- Message bubbles: sender's messages right-aligned with `bg-indigo-500 text-white`, others left-aligned with `bg-gray-100`.
