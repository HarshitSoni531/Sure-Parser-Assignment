// src/components/Navbar.jsx
import {
  Flex,
  Text,
  Button,
  HStack,
  Link as ChakraLink,
} from "@chakra-ui/react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";

export default function Navbar() {
  const { logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = () => {
    logout();
    nav("/login");
  };

  return (
    <Flex
      as="nav"
      bg="white"
      boxShadow="sm"
      align="center"
      justify="space-between"
      px={{ base: 4, md: 10 }}
      py={4}
      position="sticky"
      top="0"
      zIndex="1000"
      borderBottom="1px solid"
      borderColor="gray.100"
    >
      {/* Brand */}
      <Text
        fontWeight="bold"
        fontSize="xl"
        color="blue.600"
        letterSpacing="wide"
      >
        Sure Finance
      </Text>

      {/* Links + Logout */}
      <HStack spacing={{ base: 3, md: 6 }} align="center">
        <ChakraLink
          as={RouterLink}
          to="/upload"
          fontWeight="medium"
          color="gray.600"
          _hover={{ color: "blue.600", textDecoration: "none" }}
        >
          Upload
        </ChakraLink>

        <ChakraLink
          as={RouterLink}
          to="/statements"
          fontWeight="medium"
          color="gray.600"
          _hover={{ color: "blue.600", textDecoration: "none" }}
        >
          Statements
        </ChakraLink>

        <Button
          colorScheme="red"
          variant="solid"
          size="sm"
          onClick={handleLogout}
          rounded="md"
          px={4}
          fontWeight="semibold"
        >
          Logout
        </Button>
      </HStack>
    </Flex>
  );
}
