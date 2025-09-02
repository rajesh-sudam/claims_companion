import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:4000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// You can add interceptors here for request/response handling, e.g., auth tokens
api.interceptors.request.use(
  (config) => {
    // Example: Add authorization token
    const token = localStorage.getItem('jwt_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Example: Handle global API errors
    // if (error.response && error.response.status === 401) {
    //   // Redirect to login or refresh token
    // }
    return Promise.reject(error);
  }
);

export default api;
