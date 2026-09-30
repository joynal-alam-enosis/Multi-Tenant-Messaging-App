# Frontend Rules

These rules apply to all code within the `frontend/` directory.

## TypeScript Standards
- Strict mode enabled — **no `any` types** unless absolutely necessary and documented.
- Use `interface` for object shapes, `type` for unions/intersections.
- Export types from `src/types/index.ts`.
- Use `const` by default; `let` only when reassignment is needed; **never** `var`.

## React Patterns
- Functional components only — no class components.
- Custom hooks for all data fetching (prefix with `use`).
- Every data-fetching component must handle: **loading**, **error**, and **empty** states.
- Use `React.memo` only when profiling shows a real performance issue.

## State Management
- **Server state**: TanStack Query (`useQuery`, `useMutation`, `useQueryClient`).
- **UI state**: React `useState` / `useReducer` (selected filter, search input, etc.).
- **Never** store server data in `useState` — always use TanStack Query cache.

## API Client
- All HTTP calls go through `src/api/` modules.
- Components **never** call `fetch()` or `axios` directly.
- Use the shared Axios instance from `src/api/client.ts`.

## WebSocket
- Single connection per authenticated user via `useWebSocket` hook.
- **Always** deduplicate messages by `message.id` when updating query cache.
- Use `queryClient.setQueryData` for optimistic updates.
- Use `queryClient.invalidateQueries` for inbox refreshes.

## Styling
- Tailwind CSS utility classes — no custom CSS files unless absolutely necessary.
- Follow the project color scheme: `indigo` primary, `gray` secondary.
- Responsive by default — use `sm:`, `md:`, `lg:` breakpoints.

## Imports
- Use absolute imports from `src/` (configured via `tsconfig.json` paths).
- Group imports: React → third-party → local modules → types → styles.

## File Naming
- Components: `PascalCase.tsx` (e.g., `MessageBubble.tsx`).
- Hooks: `camelCase.ts` prefixed with `use` (e.g., `useMessages.ts`).
- API modules: `camelCase.ts` (e.g., `conversations.ts`).
- Utility modules: `camelCase.ts` (e.g., `formatTime.ts`).
