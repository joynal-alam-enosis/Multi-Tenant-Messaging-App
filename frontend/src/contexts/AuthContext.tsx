import React, { createContext, useContext, useState, useEffect } from "react";
import { globalSignOut } from "../api/cognito";
import {
  ACCESS_TOKEN_KEY,
  AUTH_USER_KEY,
  ID_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
} from "../api/client";
import type { CognitoTokens, User } from "../types";

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (tokens: CognitoTokens | string, user: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function persistSession(accessToken: string, user: User, extra?: Partial<CognitoTokens>): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(AUTH_USER_KEY, JSON.stringify(user));
  if (extra?.refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, extra.refreshToken);
  }
  if (extra?.idToken) {
    localStorage.setItem(ID_TOKEN_KEY, extra.idToken);
  }
}

function clearSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(ID_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem(AUTH_USER_KEY);
    return stored ? (JSON.parse(stored) as User) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(ACCESS_TOKEN_KEY));

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setToken(null);
    };
    window.addEventListener("auth:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("auth:unauthorized", handleUnauthorized);
  }, []);

  const login = (tokens: CognitoTokens | string, newUser: User) => {
    if (typeof tokens === "string") {
      persistSession(tokens, newUser);
      setToken(tokens);
    } else {
      persistSession(tokens.accessToken, newUser, tokens);
      setToken(tokens.accessToken);
    }
    setUser(newUser);
  };

  const logout = () => {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    if (accessToken && accessToken.split(".").length === 3) {
      void globalSignOut(accessToken);
    }
    clearSession();
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
