// src/lib/api.js
import axios from "axios";

/**
 * Axios client
 * - Base URL from Vite env or defaults to local FastAPI
 * - Attaches Authorization: Bearer <token> from localStorage automatically
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://127.0.0.1:8000",
  withCredentials: false,
});

// attach JWT for every request if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/** -----------------------
 *  Helper functions (optional)
 *  You can keep using `api.post(...)` directly if you prefer.
 *  ----------------------*/
export async function loginUser(email, password) {
  const res = await api.post("/login", { email, password });
  return res.data;
}

export async function registerUser(email, password) {
  const res = await api.post("/register", { email, password });
  return res.data;
}

export async function uploadStatement(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post("/statements/upload", form);
  return res.data;
}

export async function getStatements() {
  const res = await api.get("/statements/");
  return res.data;
}

export async function getStatement(id) {
  const res = await api.get(`/statements/${id}`);
  return res.data;
}

// default export: axios instance (so `import api from "../lib/api"` works)
export default api;
