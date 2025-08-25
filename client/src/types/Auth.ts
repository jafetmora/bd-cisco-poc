export type LoginResponse = {
  access_token: string;
  token_type: "bearer" | string;
};

export type JwtPayload = {
  sub?: string;
  iat?: number; // issued-at (seconds)
  exp?: number; // expiry (seconds)
  [k: string]: unknown;
};

export type AuthState = {
  token: string | null;
  tokenType: string | null;
  payload: JwtPayload | null;
};
