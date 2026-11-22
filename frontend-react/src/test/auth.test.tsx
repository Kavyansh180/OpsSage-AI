import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { LoginPage } from '../pages/LoginPage';
import { AuthProvider } from '../context/AuthContext';

const renderLoginPage = () => {
  return render(
    <AuthProvider>
      <BrowserRouter>
        <LoginPage />
      </BrowserRouter>
    </AuthProvider>
  );
};

describe('LoginPage Component', () => {
  it('renders branding and login form elements', () => {
    renderLoginPage();
    expect(screen.getByText('OpsSage AI')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('engineer@company.internal')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument();
    expect(screen.getByText('Sign In to Command Center')).toBeInTheDocument();
  });

  it('switches between Sign In and Create Account tabs', () => {
    renderLoginPage();
    const createAccountTab = screen.getByText('Create Account');
    fireEvent.click(createAccountTab);

    expect(screen.getByPlaceholderText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('Create SRE Account')).toBeInTheDocument();

    const signInTab = screen.getByText('Sign In');
    fireEvent.click(signInTab);
    expect(screen.getByText('Sign In to Command Center')).toBeInTheDocument();
  });

  it('validates password length on registration tab', async () => {
    renderLoginPage();
    fireEvent.click(screen.getByText('Create Account'));

    fireEvent.change(screen.getByPlaceholderText('Jane Doe'), {
      target: { value: 'Test User' },
    });
    fireEvent.change(screen.getByPlaceholderText('jane@company.internal'), {
      target: { value: 'test@company.internal' },
    });
    fireEvent.change(screen.getByPlaceholderText('••••••••'), {
      target: { value: 'short' },
    });

    fireEvent.click(screen.getByText('Create SRE Account'));
    expect(
      await screen.findByText('Password must be at least 8 characters long.')
    ).toBeInTheDocument();
  });
});
