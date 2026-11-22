import { describe, it, expect } from 'vitest';
import { API_BASE_URL } from '../services/api';

describe('Centralized API Configuration', () => {
  it('resolves API_BASE_URL ending with /api/v1', () => {
    expect(API_BASE_URL).toContain('/api/v1');
    expect(API_BASE_URL.startsWith('http')).toBe(true);
  });
});
