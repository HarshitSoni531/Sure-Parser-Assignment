// src/Pages/Register.jsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api from "../lib/api";
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

export default function Register() {
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.post("/register", form);
      nav("/login");
    } catch (err) {
      setError(err?.response?.data?.detail || "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box bg="gray.50" minH="100vh">
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
              <Heading size="lg">Create your account</Heading>
              <Text color="gray.600" fontSize="sm">
                Use a strong password (8–64 chars).
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
                    type="email"
                    placeholder="you@example.com"
                    value={form.email}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, email: e.target.value }))
                    }
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Password</FormLabel>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    minLength={8}
                    maxLength={64}
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
                  disabled={loading}
                >
                  {loading ? "Creating..." : "Sign up"}
                </Button>
              </Stack>
            </form>

            <Text mt={6} textAlign="center" color="gray.600" fontSize="sm">
              Already have an account?{" "}
              <Link to="/login" style={{ color: "#2563eb" }}>
                Login
              </Link>
            </Text>
          </Box>
        </Flex>
      </Container>
    </Box>
  );
}
