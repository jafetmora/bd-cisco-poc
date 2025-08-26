import type { JwtPayload, LoginResponse } from "../types/Auth";

const API_BASE_URL = import.meta.env?.VITE_API_URL;

console.log("DEBUG", API_BASE_URL);

function base64UrlDecode(input: string): string {
  // handle base64url => base64
  const str = input.replace(/-/g, "+").replace(/_/g, "/");
  const pad = str.length % 4;
  const padded = pad ? str + "=".repeat(4 - pad) : str;
  return atob(padded);
}

export function decodeJwt(token: string): JwtPayload {
  try {
    const [, payload] = token.split(".");
    const json = base64UrlDecode(payload);
    return JSON.parse(json);
  } catch {
    return {} as JwtPayload;
  }
}

export class AuthService {
  private readonly loginUrl = `${API_BASE_URL}/auth/login`;

  async login(
    username: string,
    password: string,
  ): Promise<{ token: string; tokenType: string; payload: JwtPayload }> {
    const res = await fetch(this.loginUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Login failed with status ${res.status}`);
    }

    const data = (await res.json()) as LoginResponse;
    const payload = decodeJwt(data.access_token);
    return { token: data.access_token, tokenType: data.token_type, payload };
  }
}
