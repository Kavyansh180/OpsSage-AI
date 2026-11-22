import { apiClient } from './api';
import { AuthResponse, LoginPayload, RegisterPayload, User } from '../types/auth';

export const authService = {
  async login(payload: LoginPayload): Promise<AuthResponse> {
    const response = await apiClient.post<AuthResponse>('/auth/login', {
      email: payload.email.trim(),
      password: payload.password,
    });
    const data = response.data;
    if (data.access_token) {
      localStorage.setItem('opssage_token', data.access_token);
    }
    return data;
  },

  async register(payload: RegisterPayload): Promise<User> {
    const response = await apiClient.post<User>('/auth/register', {
      email: payload.email.trim(),
      password: payload.password,
      full_name: payload.full_name.trim(),
      role: payload.role || 'engineer',
    });
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    const user = response.data;
    localStorage.setItem('opssage_user', JSON.stringify(user));
    return user;
  },

  getToken(): string | null {
    return localStorage.getItem('opssage_token');
  },

  getStoredUser(): User | null {
    const raw = localStorage.getItem('opssage_user');
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  },

  logout(): void {
    localStorage.removeItem('opssage_token');
    localStorage.removeItem('opssage_user');
    window.dispatchEvent(new Event('auth:logout'));
  },
};
