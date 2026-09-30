import { DEFAULT_COGNITO_ENDPOINT, getEnvCognitoConfig, type CognitoRuntimeConfig } from "../config/cognito";
import type { CognitoTokens } from "../types";

interface CognitoAuthResult {
  AccessToken?: string;
  IdToken?: string;
  RefreshToken?: string;
}

interface CognitoInitiateAuthResponse {
  AuthenticationResult?: CognitoAuthResult;
  ChallengeName?: string;
  __type?: string;
  message?: string;
}

let cachedConfig: CognitoRuntimeConfig | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export class CognitoAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CognitoAuthError";
  }
}

async function loadCognitoConfig(): Promise<CognitoRuntimeConfig> {
  if (cachedConfig?.clientId) {
    return cachedConfig;
  }

  const envConfig = getEnvCognitoConfig();
  if (envConfig.clientId) {
    cachedConfig = envConfig;
    return cachedConfig;
  }

  const response = await fetch("/api/auth/cognito-config/");
  if (!response.ok) {
    throw new CognitoAuthError("Could not load Cognito configuration");
  }
  const body: unknown = await response.json();
  if (!isRecord(body) || typeof body.client_id !== "string" || !body.client_id) {
    throw new CognitoAuthError("Cognito client is not configured. Run bootstrap_cognito / seed.");
  }

  cachedConfig = {
    endpoint: envConfig.endpoint || DEFAULT_COGNITO_ENDPOINT,
    region: typeof body.region === "string" ? body.region : envConfig.region,
    userPoolId: typeof body.user_pool_id === "string" ? body.user_pool_id : "",
    clientId: body.client_id,
  };
  return cachedConfig;
}

async function postCognito(target: string, payload: Record<string, unknown>): Promise<CognitoInitiateAuthResponse> {
  const config = await loadCognitoConfig();
  const response = await fetch(config.endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": target,
    },
    body: JSON.stringify(payload),
  });

  const body: unknown = await response.json().catch(() => ({}));
  const parsed: CognitoInitiateAuthResponse = isRecord(body) ? (body as CognitoInitiateAuthResponse) : {};

  if (!response.ok) {
    const message = parsed.message || parsed.__type || `Cognito request failed (${response.status})`;
    throw new CognitoAuthError(message);
  }
  if (parsed.__type && !parsed.AuthenticationResult) {
    throw new CognitoAuthError(parsed.message || parsed.__type);
  }
  return parsed;
}

function tokensFromResult(result: CognitoAuthResult, previousRefresh?: string): CognitoTokens {
  if (!result.AccessToken) {
    throw new CognitoAuthError("Cognito did not return an access token");
  }
  return {
    accessToken: result.AccessToken,
    idToken: result.IdToken || "",
    refreshToken: result.RefreshToken || previousRefresh || "",
  };
}

export async function initiatePasswordAuth(email: string, password: string): Promise<CognitoTokens> {
  const config = await loadCognitoConfig();
  const response = await postCognito("AWSCognitoIdentityProviderService.InitiateAuth", {
    AuthFlow: "USER_PASSWORD_AUTH",
    ClientId: config.clientId,
    AuthParameters: {
      USERNAME: email,
      PASSWORD: password,
    },
  });

  if (response.ChallengeName) {
    throw new CognitoAuthError(`Unsupported auth challenge: ${response.ChallengeName}`);
  }
  if (!response.AuthenticationResult) {
    throw new CognitoAuthError("Cognito login failed");
  }
  return tokensFromResult(response.AuthenticationResult);
}

export async function refreshCognitoSession(refreshToken: string): Promise<CognitoTokens> {
  const config = await loadCognitoConfig();
  const response = await postCognito("AWSCognitoIdentityProviderService.InitiateAuth", {
    AuthFlow: "REFRESH_TOKEN_AUTH",
    ClientId: config.clientId,
    AuthParameters: {
      REFRESH_TOKEN: refreshToken,
    },
  });
  if (!response.AuthenticationResult) {
    throw new CognitoAuthError("Cognito token refresh failed");
  }
  return tokensFromResult(response.AuthenticationResult, refreshToken);
}

export async function globalSignOut(accessToken: string): Promise<void> {
  try {
    await postCognito("AWSCognitoIdentityProviderService.GlobalSignOut", {
      AccessToken: accessToken,
    });
  } catch {
    // Local logout still proceeds if MiniStack rejects sign-out.
  }
}
