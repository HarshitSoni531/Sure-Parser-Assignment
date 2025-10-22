// src/App.jsx
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import {
  ChakraProvider,
  extendTheme,
  ColorModeScript,
  Box,
} from "@chakra-ui/react";
import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";

import Navbar from "./components/Navbar.jsx";
import Login from "./Pages/Login.jsx";
import Register from "./Pages/Register.jsx";
import Upload from "./Pages/Upload.jsx";
import Statements from "./Pages/Statements.jsx";
import StatementView from "./Pages/StatementView.jsx";

// ======================
//  Theme Configuration
// ======================
const theme = extendTheme({
  fonts: {
    heading: "Inter, system-ui, sans-serif",
    body: "Inter, system-ui, sans-serif",
  },
  styles: {
    global: {
      body: {
        bg: "gray.50",
        color: "gray.800",
        lineHeight: "base",
      },
    },
  },
});

// ======================
//  Auth Guard
// ======================
function Private({ children }) {
  const { isAuthed } = useAuth();
  const loc = useLocation();
  return isAuthed ? (
    children
  ) : (
    <Navigate to="/login" replace state={{ from: loc }} />
  );
}

// ======================
//  App Root Component
// ======================
export default function App() {
  const location = useLocation();
  const showNavbar =
    !location.pathname.startsWith("/login") &&
    !location.pathname.startsWith("/register");

  return (
    <ChakraProvider theme={theme}>
      <ColorModeScript initialColorMode="light" />
      <AuthProvider>
        {/* Navbar only when logged in */}
        {showNavbar && <Navbar />}

        {/* Page content */}
        <Box as="main">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />

            <Route
              path="/upload"
              element={
                <Private>
                  <Upload />
                </Private>
              }
            />
            <Route
              path="/statements"
              element={
                <Private>
                  <Statements />
                </Private>
              }
            />
            <Route
              path="/statements/:id"
              element={
                <Private>
                  <StatementView />
                </Private>
              }
            />

            {/* Fallback redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Box>
      </AuthProvider>
    </ChakraProvider>
  );
}
