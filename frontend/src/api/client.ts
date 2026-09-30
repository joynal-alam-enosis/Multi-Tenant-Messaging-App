import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import { refreshCognitoSession } from "./cognito";

export const ACCESS_TOKEN_KEY = "auth_token";
export const REFRESH_TOKEN_KEY = "auth_refresh_token";
export const ID_TOKEN_KEY = "auth_id_token";
export const AUTH_USER_KEY = "auth_user";

function isJwt(token: string): boolean {
  return token.split(".").length === 3;
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function authorizationHeader(token: string): string {
  return isJwt(token) ? `Bearer ${token}` : `Token ${token}`;
}

export const apiClient = axios.create({
  baseURL: "/api",
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  const token = getStoredAccessToken();
  if (token && config.headers) {
    config.headers.Authorization = authorizationHeader(token);
  }
  return config;
});

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

async function handleUnauthorized(error: AxiosError): Promise<unknown> {
  const config = error.config as RetryConfig | undefined;
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (config && !config._retry && refreshToken) {
    config._retry = true;
    try {
      const tokens = await refreshCognitoSession(refreshToken);
      localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
      if (tokens.idToken) {
        localStorage.setItem(ID_TOKEN_KEY, tokens.idToken);
      }
      if (tokens.refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
      }
      if (config.headers) {
        config.headers.Authorization = authorizationHeader(tokens.accessToken);
      }
      return apiClient(config);
    } catch {
      // Fall through to logout.
    }
  }

  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ID_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  window.dispatchEvent(new Event("auth:unauthorized"));
  return Promise.reject(error);
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      return handleUnauthorized(error);
    }
    return Promise.reject(error);
  }
);
