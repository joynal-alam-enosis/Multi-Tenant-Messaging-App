/**
 * Cognito / MiniStack client settings.
 * Pool and client IDs are loaded from env or GET /api/auth/cognito-config/.
 */
export interface CognitoRuntimeConfig {
  endpoint: string;
  region: string;
  userPoolId: string;
  clientId: string;
}

/** Same-origin Vite proxy to MiniStack (avoids browser CORS). */
export const DEFAULT_COGNITO_ENDPOINT = "/aws-cognito";

export function getEnvCognitoConfig(): CognitoRuntimeConfig {
  return {
    endpoint: import.meta.env.VITE_AWS_ENDPOINT_URL || DEFAULT_COGNITO_ENDPOINT,
    region: import.meta.env.VITE_AWS_REGION || "us-east-1",
    userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID || "",
    clientId: import.meta.env.VITE_COGNITO_CLIENT_ID || "",
  };
}
