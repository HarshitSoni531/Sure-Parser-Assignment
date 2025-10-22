// src/Pages/StatementView.jsx
import { useEffect, useState } from "react";
import { useParams, useLocation } from "react-router-dom";
import api from "../lib/api";
import {
  Box,
  Flex,
  Spinner,
  Heading,
  Text,
  Stack,
  Divider,
  Card,
  CardBody,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Code,
} from "@chakra-ui/react";

export default function StatementView() {
  const { id } = useParams();
  const location = useLocation();

  // If we navigated from /upload, we may have the wrapped payload in state:
  // { statement: {...}, transactions: [...] }
  const preload = location.state || null;

  const [loading, setLoading] = useState(!preload);
  const [payload, setPayload] = useState(preload);

  useEffect(() => {
    if (preload) return; // already have data via navigation state
    let mounted = true;
    api
      .get(`/statements/${id}`)
      .then((res) => mounted && setPayload(res.data))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, [id, preload]);

  if (loading)
    return (
      <Flex minH="80vh" align="center" justify="center">
        <Spinner size="xl" color="blue.500" thickness="4px" />
      </Flex>
    );

  if (!payload)
    return (
      <Flex minH="80vh" align="center" justify="center">
        <Text fontSize="lg" color="gray.600">
          Not found
        </Text>
      </Flex>
    );

  // ✅ Handle BOTH shapes:
  // - Wrapped (upload): { statement: {...}, transactions: [...] }
  // - Flat (detail):    { id, issuer, ..., transactions: [...] }
  const isWrapped =
    !!payload?.statement && typeof payload.statement === "object";
  const s = isWrapped ? payload.statement : payload;
  const txs = payload.transactions || [];

  // ---------- helpers ----------
  const toNumber = (val) => {
    if (val === null || val === undefined) return null;
    const n = Number(String(val).replace(/[₹,\s]/g, ""));
    return Number.isFinite(n) ? n : null;
  };

  const formatAmount = (val) => {
    const n = toNumber(val);
    if (n === null) return "—";
    return `${n < 0 ? "-" : "+"}₹${Math.abs(n).toFixed(2)}`;
  };

  const formatDate = (d) => {
    if (!d) return "—";
    const dt = new Date(d);
    // Backend often sends "07 Jun 24" which isn't ISO; show raw if not parseable.
    return isNaN(dt.getTime())
      ? d
      : dt.toLocaleDateString("en-IN", {
          day: "2-digit",
          month: "short",
          year: "2-digit",
        });
  };

  return (
    <Box bg="gray.50" minH="100vh" py={10}>
      <Box maxW="6xl" mx="auto" px={{ base: 4, md: 6 }}>
        <Heading mb={6} size="lg" color="gray.800">
          Statement Summary
        </Heading>

        <Card rounded="xl" shadow="md" mb={8}>
          <CardBody>
            <Stack spacing={3} fontSize="sm" color="gray.700">
              <Text>
                <b>Issuer:</b> {s.issuer ?? "—"}
              </Text>
              <Text>
                <b>Card Variant:</b> {s.card_variant ?? "—"}
              </Text>
              <Text>
                <b>Last 4 Digits:</b> {s.card_last_4 ?? "—"}
              </Text>
              <Text>
                <b>Billing Cycle:</b> {s.billing_cycle ?? "—"}
              </Text>
              <Text>
                <b>Payment Due Date:</b> {s.payment_due_date ?? "—"}
              </Text>
              {"total_amount_due" in s && (
                <Text>
                  <b>Total Amount Due:</b> {formatAmount(s.total_amount_due)}
                </Text>
              )}

              {!s.issuer &&
                !s.card_variant &&
                !s.card_last_4 &&
                !s.billing_cycle &&
                !s.payment_due_date && (
                  <Text fontSize="sm" color="orange.600">
                    Heads up: These fields are empty in the API response. If
                    your PDF parsed correctly but you still see dashes, the
                    extractor may not be populating these keys.
                  </Text>
                )}
            </Stack>
          </CardBody>
        </Card>

        <Heading mb={4} size="md" color="gray.800">
          Transactions
        </Heading>

        {txs.length === 0 ? (
          <Text color="gray.500" fontSize="sm">
            No transactions found for this statement.
          </Text>
        ) : (
          <Stack spacing={4}>
            {txs.map((tx, i) => (
              <Card
                key={tx.id ?? i}
                shadow="sm"
                rounded="md"
                border="1px solid"
                borderColor="gray.100"
              >
                <CardBody>
                  <Flex justify="space-between" align="center">
                    <Stack spacing={1} minW={0}>
                      <Text fontWeight="medium" noOfLines={2}>
                        {tx.description || "—"}
                      </Text>
                      <Text fontSize="sm" color="gray.500">
                        {formatDate(tx.date)}
                      </Text>
                    </Stack>
                    <Text
                      fontWeight="semibold"
                      fontSize="md"
                      color={
                        toNumber(tx.amount) < 0
                          ? "red.500"
                          : toNumber(tx.amount) > 0
                          ? "green.600"
                          : "gray.500"
                      }
                    >
                      {formatAmount(tx.amount)}
                    </Text>
                  </Flex>
                </CardBody>
              </Card>
            ))}
          </Stack>
        )}

        {/* Inline Debug: see exactly what the API returned */}
        <Accordion allowToggle mt={10}>
          <AccordionItem border="none">
            <h2>
              <AccordionButton px={0}>
                <Box as="span" flex="1" textAlign="left" fontWeight="semibold">
                  Debug payload (
                  {isWrapped
                    ? "wrapped from /upload"
                    : "flat from /statements/:id"}
                  )
                </Box>
                <AccordionIcon />
              </AccordionButton>
            </h2>
            <AccordionPanel px={0} pt={4}>
              <Code whiteSpace="pre" display="block" p={4} w="full">
                {JSON.stringify(payload, null, 2)}
              </Code>
            </AccordionPanel>
          </AccordionItem>
        </Accordion>

        <Divider my={10} />
        <Text fontSize="xs" color="gray.400" textAlign="center">
          Statement ID: {id}
        </Text>
      </Box>
    </Box>
  );
}
