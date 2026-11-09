import { useEffect, useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Button,
  CircularProgress,
  Container,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import LogoutRoundedIcon from "@mui/icons-material/LogoutRounded";
import RefreshRoundedIcon from "@mui/icons-material/RefreshRounded";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { authSession } from "../services/authSession.js";
import { useAuth } from "../services/useAuth.js";

export function AuthStatus() {
  const { status, error } = useAuth();
  return (
    <Container maxWidth="sm" className="center-page">
      <Stack spacing={3} alignItems="center" role="status">
        <Typography variant="h5" component="h1">
          認証状態の確認
        </Typography>
        {status === "checking" ? (
          <CircularProgress aria-label="認証状態を確認中" />
        ) : (
          <>
            <Alert severity="error">{error?.message}</Alert>
            <Button
              variant="outlined"
              startIcon={<RefreshRoundedIcon />}
              onClick={() => void authSession.revalidate()}
            >
              再試行
            </Button>
          </>
        )}
      </Stack>
    </Container>
  );
}

export default function AuthRoot() {
  useEffect(() => authSession.start(), []);
  return <Outlet />;
}

export function RequireAuth() {
  const { status, session } = useAuth();
  const location = useLocation();
  const [loggingOut, setLoggingOut] = useState(false);
  const [error, setError] = useState(null);

  if (status === "checking" || status === "error") return <AuthStatus />;
  if (status !== "authenticated") {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: `${location.pathname}${location.search}${location.hash}`,
        }}
      />
    );
  }

  async function logout() {
    setLoggingOut(true);
    setError(null);
    try {
      await authSession.logout();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <Box sx={{ height: "100dvh", display: "flex", flexDirection: "column" }}>
      <AppBar
        position="static"
        color="default"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar sx={{ gap: 2 }}>
          <Typography sx={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>
            {session.user.username}
          </Typography>
          <Button
            color="inherit"
            startIcon={<LogoutRoundedIcon />}
            disabled={loggingOut}
            onClick={logout}
            sx={{ flexShrink: 0 }}
          >
            {loggingOut ? "ログアウト中…" : "ログアウト"}
          </Button>
        </Toolbar>
      </AppBar>
      {error && (
        <Alert severity="error" onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <Box component="main" sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <Outlet />
      </Box>
    </Box>
  );
}
