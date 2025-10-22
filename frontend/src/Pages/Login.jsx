// src/Pages/Login.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../lib/api.js";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  Alert,
  AlertIcon,
  Box,
  Button,
  Container,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Stack,
  Text,
} from "@chakra-ui/react";

function extractApiError(err) {
  const d = err?.response?.data;
  if (!d) return "Network error";
  if (typeof d?.detail === "string") return d.detail;
  if (Array.isArray(d?.detail))
    return d.detail
      .map((e) => e?.msg || "")
      .filter(Boolean)
      .join("; ");
  if (d?.message) return d.message;
  try {
    return JSON.stringify(d);
  } catch {
    return "Unexpected error";
  }
}

export default function Login() {
  const nav = useNavigate();
  const { login } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const { data } = await api.post("/login", form);
      login(data.access_token);
      nav("/upload");
    } catch (err) {
      setError(extractApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box bg="gray.50" minH="100vh">
      {/* Centers the card on the page, regardless of viewport width */}
      <Container maxW="lg" px={{ base: 4, md: 6 }}>
        <Flex minH="80vh" align="center" justify="center">
          <Box
            bg="white"
            w="full"
            rounded="2xl"
            shadow="md"
            p={{ base: 6, md: 8 }}
            border="1px solid"
            borderColor="gray.100"
          >
            <Stack spacing={1} mb={6} textAlign="center">
              <Heading size="lg">Welcome back</Heading>
              <Text color="gray.600" fontSize="sm">
                Log in to continue to your dashboard.
              </Text>
            </Stack>

            {error && (
              <Alert status="error" mb={4} rounded="md">
                <AlertIcon />
                {error}
              </Alert>
            )}

            <form onSubmit={submit}>
              <Stack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Email</FormLabel>
                  <Input
                    placeholder="you@example.com"
                    type="email"
                    value={form.email}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, email: e.target.value }))
                    }
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Password</FormLabel>
                  <Input
                    placeholder="••••••••"
                    type="password"
                    value={form.password}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, password: e.target.value }))
                    }
                  />
                </FormControl>

                <Button
                  type="submit"
                  isLoading={loading}
                  colorScheme="blue"
                  size="lg"
                  w="full"
                >
                  Login
                </Button>
              </Stack>
            </form>

            <Text mt={6} textAlign="center" color="gray.600" fontSize="sm">
              No account?{" "}
              <Link to="/register" style={{ color: "#2563eb" }}>
                Create one
              </Link>
            </Text>
          </Box>
        </Flex>
      </Container>
    </Box>
  );
}
