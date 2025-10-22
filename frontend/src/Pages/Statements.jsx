// src/Pages/Statements.jsx
import { useEffect, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import api from "../lib/api";
import {
  Box,
  Heading,
  SimpleGrid,
  Text,
  Stack,
  Flex,
  Spinner,
  Card,
  CardBody,
  LinkBox,
  LinkOverlay,
  Badge,
  Alert,
  AlertIcon,
} from "@chakra-ui/react";

export default function Statements() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/statements");
        setItems(Array.isArray(data) ? data : []);
      } catch (e) {
        setErr(
          e?.response?.data?.detail ||
            e?.message ||
            "Failed to load statements."
        );
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toNumber = (val) => {
    if (val === null || val === undefined) return null;
    const n = Number(String(val).replace(/[₹,\s]/g, ""));
    return Number.isFinite(n) ? n : null;
  };

  const formatAmount = (val) => {
    const n = toNumber(val);
    if (n === null) return "—";
    return `₹${Math.abs(n).toFixed(2)}`;
  };

  if (loading) {
    return (
      <Flex minH="80vh" align="center" justify="center">
        <Spinner size="xl" color="blue.500" thickness="4px" />
      </Flex>
    );
  }

  return (
    <Box bg="gray.50" minH="100vh" py={10}>
      <Box maxW="6xl" mx="auto" px={{ base: 4, md: 6 }}>
        <Heading mb={6} size="lg" color="gray.800">
          Your Statements
        </Heading>

        {err && (
          <Alert status="error" mb={6} rounded="md">
            <AlertIcon />
            {err}
          </Alert>
        )}

        {items.length === 0 ? (
          <Box
            bg="white"
            border="1px solid"
            borderColor="gray.200"
            rounded="xl"
            p={8}
            textAlign="center"
            color="gray.600"
          >
            <Heading size="md" mb={2} color="gray.800">
              No statements yet
            </Heading>
            <Text fontSize="sm">
              Upload your first PDF statement to see it here.
            </Text>
          </Box>
        ) : (
          <SimpleGrid columns={{ base: 1, sm: 2, lg: 3 }} spacing={6}>
            {items.map((s) => {
              const totalDue = toNumber(s.total_amount_due);
              return (
                <LinkBox
                  as={Card}
                  key={s.id}
                  rounded="xl"
                  shadow="md"
                  border="1px solid"
                  borderColor="gray.200"
                  _hover={{
                    shadow: "xl",
                    transform: "translateY(-4px)",
                    transition: "0.2s ease-in-out",
                  }}
                >
                  <CardBody>
                    <Flex justify="space-between" align="start" gap={3}>
                      <Stack spacing={1} minW={0}>
                        <Text
                          textTransform="uppercase"
                          color="gray.500"
                          fontSize="xs"
                          fontWeight="semibold"
                          letterSpacing="wide"
                          isTruncated
                          title={s.issuer || ""}
                        >
                          {s.issuer || "—"}
                        </Text>

                        <LinkOverlay as={RouterLink} to={`/statements/${s.id}`}>
                          <Text
                            fontSize="lg"
                            fontWeight="medium"
                            color="gray.800"
                            noOfLines={1}
                            title={s.card_variant || ""}
                          >
                            {s.card_variant || "—"}
                          </Text>
                        </LinkOverlay>

                        <Text
                          mt={2}
                          fontSize="sm"
                          color="gray.600"
                          noOfLines={2}
                        >
                          {s.billing_cycle || "—"}
                        </Text>
                      </Stack>

                      <Stack
                        spacing={1}
                        textAlign="right"
                        fontSize="sm"
                        color="gray.600"
                        flexShrink={0}
                        minW="140px"
                      >
                        <Text>Last 4: {s.card_last_4 || "—"}</Text>
                        <Text>Due: {s.payment_due_date || "—"}</Text>
                        {totalDue !== null && (
                          <Badge
                            mt={1}
                            colorScheme="blue"
                            variant="subtle"
                            alignSelf="flex-end"
                          >
                            Due {formatAmount(totalDue)}
                          </Badge>
                        )}
                      </Stack>
                    </Flex>
                  </CardBody>
                </LinkBox>
              );
            })}
          </SimpleGrid>
        )}
      </Box>
    </Box>
  );
}
