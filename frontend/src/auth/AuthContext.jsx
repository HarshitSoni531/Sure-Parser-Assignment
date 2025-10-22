import { createContext, useContext, useEffect, useState } from "react";
import api from "../lib/api";

const AuthCtx = createContext();

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("token"));

  const login = (jwt) => {
    localStorage.setItem("token", jwt);
    setToken(jwt);
    // optional but nice to have:
    api.defaults.headers.common.Authorization = `Bearer ${jwt}`;
  };

  const logout = () => {
    localStorage.removeItem("token");
    setToken(null);
    delete api.defaults.headers.common.Authorization;
  };

  const isAuthed = !!token;

  // keep axios in sync on refresh
  useEffect(() => {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  return (
    <AuthCtx.Provider value={{ token, isAuthed, login, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
