import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { fetchCurrentUser } from "../api/auth";
import { ACCESS_TOKEN_KEY, ID_TOKEN_KEY, REFRESH_TOKEN_KEY } from "../api/client";
import { CognitoAuthError, initiatePasswordAuth } from "../api/cognito";
import { useAuth } from "../contexts/AuthContext";

export const LoginPage: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) {
      navigate("/", { replace: true });
    }
  }, [user, navigate]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      const tokens = await initiatePasswordAuth(email, password);
      localStorage.setItem(ACCESS_TOKEN_KEY, tokens.accessToken);
      if (tokens.refreshToken) {
        localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
      }
      if (tokens.idToken) {
        localStorage.setItem(ID_TOKEN_KEY, tokens.idToken);
      }
      const profile = await fetchCurrentUser();
      login(tokens, profile);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      if (err instanceof CognitoAuthError) {
        setError(err.message);
      } else {
        setError("Login failed");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-100">
      <div className="w-full max-w-md p-8 bg-white rounded shadow-md">
        <h2 className="mb-6 text-2xl font-bold text-center text-gray-800">Login</h2>
        <p className="mb-4 text-sm text-center text-gray-500">
          Sign in with Cognito (demo password: Password123!)
        </p>
        {error && <p className="mb-4 text-sm text-red-600 bg-red-50 p-2 rounded">{error}</p>}
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block mb-1 text-sm font-medium text-gray-700">Email</label>
            <input
              type="email"
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring focus:ring-blue-200"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </div>
          <div className="mb-6">
            <label className="block mb-1 text-sm font-medium text-gray-700">Password</label>
            <input
              type="password"
              className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring focus:ring-blue-200"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full px-4 py-2 text-white bg-blue-600 rounded hover:bg-blue-700 focus:outline-none disabled:opacity-60"
          >
            {isSubmitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
};
