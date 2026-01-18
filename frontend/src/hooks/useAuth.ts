import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-hot-toast';
import api from '@/services/api';
import { useAuthStore } from '@/store/authStore';
import type { LoginRequest, LoginResponse } from '@/types';

export function useLogin() {
  const setAuth = useAuthStore((state) => state.setAuth);
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const response = await api.post<LoginResponse>('/auth/login', credentials);
      return response.data;
    },
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
      toast.success('Welcome back!');
      navigate('/');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Invalid credentials');
    },
  });
}

export function useRegister() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: async (data: {
      email: string;
      password: string;
      full_name: string;
    }) => {
      const response = await api.post('/auth/register', data);
      return response.data;
    },
    onSuccess: () => {
      toast.success('Registration successful! Please log in.');
      navigate('/login');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Registration failed');
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((state) => state.logout);
  const navigate = useNavigate();

  return () => {
    logout();
    toast.success('Logged out successfully');
    navigate('/login');
  };
}
