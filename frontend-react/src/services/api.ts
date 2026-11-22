import axios, { AxiosError } from 'axios';

// Centralized API Base URL resolution:
// 1. import.meta.env.VITE_API_BASE_URL if explicitly set
// 2. Production AWS API Gateway HTTP API default fallback
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || 'https://iulno515v4.execute-api.ap-south-1.amazonaws.com/api/v1';

// Ensure base URL cleanly ends with /api/v1
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, '').endsWith('/api/v1')
  ? rawBaseUrl.replace(/\/+$/, '')
  : `${rawBaseUrl.replace(/\/+$/, '')}/api/v1`;

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Inject JWT Bearer Token if present
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('opssage_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Extract clean error message and handle 401
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | Array<{ msg?: string }>; message?: string }>) => {
    let message = 'An unexpected network error occurred.';
    
    if (error.response) {
      const data = error.response.data;
      if (typeof data?.detail === 'string') {
        message = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
        message = data.detail[0].msg;
      } else if (data?.message) {
        message = data.message;
      } else {
        message = `Server returned HTTP ${error.response.status}`;
      }

      // If token expired or invalid, clear stored session
      if (error.response.status === 401) {
        localStorage.removeItem('opssage_token');
        localStorage.removeItem('opssage_user');
        window.dispatchEvent(new Event('auth:unauthorized'));
      }
    } else if (error.request) {
      message = 'Could not connect to OpsSage backend API. Please check network connectivity.';
    }

    return Promise.reject(new Error(message));
  }
);
