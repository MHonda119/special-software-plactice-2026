import { useState } from "react";
import {
  Alert,
  Button,
  Container,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import LoginRoundedIcon from "@mui/icons-material/LoginRounded";
import { Navigate, useLocation } from "react-router-dom";
import { authSession } from "../services/authSession.js";
import { useAuth } from "../services/useAuth.js";
import { AuthStatus } from "./AuthRoot.jsx";

export default function LoginPage() {
  const { status, reason } = useAuth();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (status === "checking" || status === "error") return <AuthStatus />;
  if (status === "authenticated") {
    const from = location.state?.from;
    const destination =
      typeof from === "string" &&
      from.startsWith("/") &&
      !from.startsWith("//") &&
      !from.startsWith("/login")
        ? from
        : "/menu";
    return <Navigate to={destination} replace />;
  }

  async function submit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await authSession.login({ username, password });
    } catch (failure) {
      setError(failure.message);
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Container maxWidth="xs" className="center-page">
      <Stack
        component="form"
        spacing={3}
        onSubmit={submit}
        sx={{ width: "100%" }}
        aria-busy={submitting}
      >
        <Typography variant="h4" component="h1" align="center">
          ログイン
        </Typography>
        {reason === "expired" && (
          <Alert severity="info">
            セッションの有効期限が切れました。再度ログインしてください。
          </Alert>
        )}
        {error && <Alert severity="error">{error}</Alert>}
        <TextField
          label="ユーザー名"
          name="username"
          autoComplete="username"
          autoFocus
          required
          fullWidth
          value={username}
          disabled={submitting}
          onChange={(event) => setUsername(event.target.value)}
        />
        <TextField
          label="パスワード"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          fullWidth
          value={password}
          disabled={submitting}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button
          type="submit"
          variant="contained"
          size="large"
          disabled={submitting}
          startIcon={<LoginRoundedIcon />}
        >
          {submitting ? "ログイン中…" : "ログイン"}
        </Button>
      </Stack>
    </Container>
  );
}
