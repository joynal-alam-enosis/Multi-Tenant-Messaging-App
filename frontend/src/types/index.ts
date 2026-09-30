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
  tenant_id: string;
  tenant_name: string;
}

export interface Conversation {
  id: string;
  other_participant: User;
  last_message: string | null;
  last_activity_at: string;
  created_at: string;
  is_starred: boolean;
  unread_count: number;
}

export interface Message {
  id: string;
  sender: User;
  content: string;
  is_read: boolean;
  created_at: string;
}

export interface ExportTask {
  id: string;
  status: "pending" | "processing" | "completed" | "failed";
}

export interface CognitoTokens {
  accessToken: string;
  idToken: string;
  refreshToken: string;
}
