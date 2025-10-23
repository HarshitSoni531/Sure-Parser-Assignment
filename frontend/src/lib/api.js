// src/lib/api.js
import axios from "axios";

/**
 * Axios client
 * - Base URL from Vite env or defaults to your deployed FastAPI
 * - Attaches Authorization: Bearer <token> from localStorage automatically
 */
const envBase = import.meta.env.VITE_API_URL;
// Default to the Render URL if no env is provided
let baseURL = envBase || "https://sure-parser-assignment-1.onrender.com";
// guard against accidental trailing slashes
baseURL = baseURL.replace(/\/+$/, "");

const api = axios.create({
  baseURL,
  withCredentials: false,
  timeout: 30000,
});

// Attach JWT for every request if present
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

export async function uploadStatement(file, issuer = "auto") {
  const form = new FormData();
  form.append("file", file);
  form.append("issuer", issuer);
  const res = await api.post("/statements/upload", form);
  return res.data;
}

export async function getStatements() {
  const res = await api.get("/statements");
  return res.data;
}

export async function getStatement(id) {
  const res = await api.get(`/statements/${id}`);
  return res.data;
}

// default export: axios instance (so `import api from "../lib/api"` works)
export default api;
