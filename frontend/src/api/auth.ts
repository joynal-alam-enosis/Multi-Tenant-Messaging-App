import { apiClient } from "./client";
import type { User } from "../types";

export async function fetchCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>("/auth/me/");
  return response.data;
}
