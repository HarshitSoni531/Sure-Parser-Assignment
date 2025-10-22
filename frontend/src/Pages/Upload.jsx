// src/Pages/Upload.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../lib/api";
import { useAuth } from "../auth/AuthContext.jsx";
import {
  Box,
  Button,
  Card,
  CardBody,
  Container,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Select,
  Spinner,
  Stack,
  Text,
  useColorModeValue,
} from "@chakra-ui/react";

export default function Upload() {
  const nav = useNavigate();
  const { isAuthed } = useAuth();

  const [file, setFile] = useState(null);
  const [issuer, setIssuer] = useState("auto");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");

  const onSelect = (f) => {
    setError("");
    setOk("");
    if (!f) return setFile(null);
    if (f.type !== "application/pdf") {
      setError("Only PDF files are supported.");
      return setFile(null);
    }
    if (f.size > 25 * 1024 * 1024) {
      setError("File is too large (max 25 MB).");
      return setFile(null);
    }
    setFile(f);
  };

  const onDrop = (e) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) onSelect(f);
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setOk("");

    if (!isAuthed) return setError("You must be logged in to upload.");
    if (!file) return setError("Please choose a PDF statement.");

    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("issuer", issuer);
      const { data } = await api.post("/statements/upload", form);
      setOk("Statement uploaded & parsed successfully.");
      const id = data?.statement?.id;
      if (id) nav(`/statements/${id}`);
    } catch (err) {
      const d = err?.response?.data;
      const detail =
        typeof d?.detail === "string"
          ? d.detail
          : Array.isArray(d?.detail)
          ? d.detail
              .map((x) => x?.msg)
              .filter(Boolean)
              .join("; ")
          : d?.message || "Upload failed";
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const teal = useColorModeValue("#0f9da3", "teal.600");

  return (
    <Box bg="gray.50" minH="100vh" py={10}>
      <Container maxW="6xl" px={{ base: 4, md: 6 }}>
        <Flex direction={{ base: "column", lg: "row" }} gap={6} align="stretch">
          {/* Dropzone Section */}
          <Card
            flex="2"
            shadow="md"
            rounded="2xl"
            border="1px solid"
            borderColor="gray.200"
          >
            <CardBody
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              textAlign="center"
            >
              <Box
                bg={teal}
                color="white"
                borderRadius="2xl"
                border="2px dashed rgba(255,255,255,0.7)"
                p={{ base: 10, md: 14 }}
              >
                <Stack align="center" spacing={5}>
                  <Heading size="md">Upload your credit card statement</Heading>
                  <Text fontSize="sm" opacity={0.9}>
                    PDF only. We support SBI & HDFC.
                  </Text>

                  <Button
                    as="label"
                    colorScheme="whiteAlpha"
                    variant="solid"
                    cursor="pointer"
                  >
                    Choose PDF
                    <Input
                      type="file"
                      accept="application/pdf"
                      display="none"
                      onChange={(e) => onSelect(e.target.files?.[0] || null)}
                    />
                  </Button>

                  {file && (
                    <Text fontSize="sm" opacity={0.9}>
                      Selected:{" "}
                      <Text as="span" fontWeight="medium">
                        {file.name}
                      </Text>{" "}
                      <Text as="span" opacity={0.8}>
                        ({(file.size / 1024 / 1024).toFixed(2)} MB)
                      </Text>
                    </Text>
                  )}

                  {ok && (
                    <Box
                      bg="whiteAlpha.200"
                      px={4}
                      py={2}
                      rounded="md"
                      fontSize="sm"
                      fontWeight="medium"
                    >
                      {ok}
                    </Box>
                  )}

                  {loading && <Spinner size="md" color="whiteAlpha.800" />}
                </Stack>
              </Box>
            </CardBody>
          </Card>

          {/* Options Panel */}
          <Card
            flex="1"
            shadow="md"
            rounded="2xl"
            border="1px solid"
            borderColor="gray.200"
          >
            <CardBody>
              <Heading size="md" mb={4}>
                Options
              </Heading>
              <form onSubmit={submit}>
                <Stack spacing={4}>
                  <FormControl>
                    <FormLabel fontSize="sm" color="gray.600">
                      Issuer
                    </FormLabel>
                    <Select
                      value={issuer}
                      onChange={(e) => setIssuer(e.target.value)}
                    >
                      <option value="auto">Auto-detect</option>
                      <option value="SBI">SBI</option>
                      <option value="HDFC">HDFC</option>
                    </Select>
                  </FormControl>

                  {error && (
                    <Box
                      bg="red.50"
                      color="red.700"
                      fontSize="sm"
                      p={3}
                      rounded="md"
                    >
                      {error}
                    </Box>
                  )}

                  <Button
                    colorScheme="blue"
                    type="submit"
                    isLoading={loading}
                    isDisabled={loading || !file}
                  >
                    {loading ? "Parsing..." : "Parse Statement"}
                  </Button>
                </Stack>
              </form>

              <Text mt={5} fontSize="xs" color="gray.500">
                Tip: Drag & drop your PDF anywhere inside the dashed area on the
                left.
              </Text>
            </CardBody>
          </Card>
        </Flex>
      </Container>
    </Box>
  );
}
