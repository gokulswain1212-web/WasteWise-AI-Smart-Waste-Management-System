import api from "./api";

export interface LoginResponse {
  email: string;
}

export interface SessionResponse {
  email: string | null;
}

export async function login(email: string, password: string): Promise<void> {
  await api.post<LoginResponse>("/api/v1/auth/login", { email, password });
}

export async function getSession(): Promise<SessionResponse> {
  const response = await api.get<SessionResponse>("/api/v1/auth/session");
  return response.data;
}

export async function logout(): Promise<void> {
  await api.post("/api/v1/auth/logout");
}
