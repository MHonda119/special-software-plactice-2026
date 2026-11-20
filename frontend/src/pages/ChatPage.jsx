import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Container,
  Paper,
  Stack,
  TextField,
  Box,
  List,
  ListItem,
  ListItemText,
  Avatar,
  Chip,
  CircularProgress,
  LinearProgress,
  Tooltip,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SendIcon from "@mui/icons-material/Send";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  getMessages as apiGetMessages,
  sendMessage as apiSendMessage,
  agentApi,
} from "../services/apiClient.js";

export default function ChatPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessionId: sessionParam } = useParams();
  const searchParams = useMemo(
    () => new URLSearchParams(location.search),
    [location.search],
  );
  const agentId = searchParams.get("agentId");
  const agentName = searchParams.get("agentName") || "";
  const agentUsecase = searchParams.get("usecaseType") || "";
  const isAgentChat = Boolean(agentId);
  const isReAct = isAgentChat && agentUsecase === "REACT_CHAT";
  const agentQuery = useMemo(() => {
    if (!isAgentChat) return "";
    const q = new URLSearchParams({
      agentId,
      agentName,
      usecaseType: agentUsecase,
    });
    return `?${q.toString()}`;
  }, [agentId, agentName, agentUsecase, isAgentChat]);

  const [activeSessionId, setActiveSessionId] = useState(sessionParam || null);
  useEffect(() => {
    setActiveSessionId(sessionParam || null);
  }, [sessionParam]);

  const [sessionTitle, setSessionTitle] = useState(agentName || "");
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const [input, setInput] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const [executionState, setExecutionState] = useState("idle");
  const [historyLoading, setHistoryLoading] = useState(Boolean(sessionParam));
  const sending = executionState === "running";
  const inputLength = Array.from(input.trim()).length;
  const inputTooLong = isReAct && inputLength > 2000;
  const sendPendingRef = useRef(false);
  const messageListRef = useRef(null);

  const visibleMessages = useMemo(
    () => messages.filter((m) => m.role !== "system"),
    [messages],
  );

  useEffect(() => {
    let cancelled = false;
    if (!activeSessionId) {
      setMessages([]);
      setHistoryLoading(false);
      return;
    }
    setHistoryLoading(true);
    (async () => {
      setError(null);
      try {
        const ms = await apiGetMessages(activeSessionId);
        if (cancelled) return;
        // Map backend fields to UI as needed
        const mapped = ms.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          createdAt: m.created_at || m.createdAt || new Date().toISOString(),
          citations: m.metadata?.citations,
          usage: m.usage,
        }));
        setMessages((previous) => {
          const usageById = new Map(
            previous.map((message) => [message.id, message.usage]),
          );
          return mapped.map((message) => ({
            ...message,
            usage: message.usage || usageById.get(message.id),
          }));
        });
        setExecutionState(
          mapped.some((message) => message.role === "assistant")
            ? "completed"
            : "idle",
        );
        // Derive title from first user message
        const firstUser = mapped.find((x) => x.role === "user");
        setSessionTitle(
          agentName ||
            (firstUser ? firstUser.content.slice(0, 20) : "New Chat"),
        );
      } catch (failure) {
        if (cancelled) return;
        setError(failure.message);
        setExecutionState("failed");
        setMessages([]);
        setSessionTitle(agentName || "New Chat");
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeSessionId, agentName]);

  useEffect(() => {
    const list = messageListRef.current;
    list?.scrollTo({ top: list.scrollHeight, behavior: "smooth" });
  }, [visibleMessages]);

  const canSend = useMemo(() => {
    if (!input.trim() || sending || historyLoading || inputTooLong)
      return false;
    if (isAgentChat) return true;
    return Boolean(activeSessionId);
  }, [
    input,
    isAgentChat,
    activeSessionId,
    sending,
    historyLoading,
    inputTooLong,
  ]);

  const handleSend = async () => {
    if (!canSend || sendPendingRef.current) return;
    sendPendingRef.current = true;
    setExecutionState("running");
    setError(null);
    const text = input.trim();
    const temporaryId = `temp-${Date.now()}`;
    setInput("");
    try {
      // Optimistic append user message
      const userMsg = {
        id: temporaryId,
        role: "user",
        content: text,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      if (isAgentChat) {
        const execResult = await agentApi.execute(agentId, {
          input: text,
          session_uuid: activeSessionId || undefined,
        });
        const nextSession = execResult.session_uuid;
        if (!activeSessionId && nextSession) {
          setActiveSessionId(nextSession);
          if (isAgentChat) {
            navigate(`/chat/${nextSession}${agentQuery}`, { replace: true });
          }
        }
        const assistant = execResult.result?.message || {};
        const citations = execResult.result?.citations || [];
        const assistantMsg = {
          id: assistant.id || `assistant-${Date.now()}`,
          role: assistant.role || "assistant",
          content: assistant.content || "",
          createdAt: new Date().toISOString(),
          citations,
          usage: execResult.usage,
        };
        setMessages((prev) => [...prev, assistantMsg]);
        setExecutionState("completed");
        if (!sessionTitle) setSessionTitle(agentName || text.slice(0, 20));
        return;
      }

      const result = await apiSendMessage(activeSessionId, text);
      // result: { session_uuid, assistant_message: {id, role, content}, usage }
      const assistant = result.assistant_message;
      const assistantMsg = {
        id: assistant.id,
        role: assistant.role,
        content: assistant.content,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setExecutionState("completed");
      if (!sessionTitle) setSessionTitle(text.slice(0, 20));
    } catch (e) {
      setError(e.message);
      setExecutionState("failed");
      if (isReAct) {
        setMessages((previous) =>
          previous.filter((message) => message.id !== temporaryId),
        );
        setInput(text);
      }
    } finally {
      sendPendingRef.current = false;
    }
  };

  return (
    <Box className="chat-shell">
      <AppBar position="static">
        <Toolbar>
          <IconButton
            aria-label="メニューへ戻る"
            color="inherit"
            edge="start"
            onClick={() => navigate("/menu")}
          >
            <ArrowBackIcon />
          </IconButton>
          <Typography
            variant="h6"
            sx={{ ml: 1, minWidth: 0, overflowWrap: "anywhere" }}
          >
            {sessionTitle || "New Chat"}
          </Typography>
        </Toolbar>
      </AppBar>
      {error && <Alert severity="error">{error}</Alert>}
      <Container
        maxWidth="md"
        className="chat-content"
        style={{
          paddingTop: 16,
          paddingBottom: 16,
          alignItems: isReAct ? "flex-start" : undefined,
          minHeight: isReAct ? 0 : undefined,
        }}
      >
        <Box
          aria-busy={sending || historyLoading}
          sx={{
            width: "100%",
            display: "flex",
            flexDirection: "column",
            gap: 2,
            height: isReAct ? "100%" : undefined,
            minHeight: isReAct ? 0 : undefined,
          }}
        >
          {isReAct && (
            <Stack
              direction="row"
              alignItems="center"
              spacing={1}
              sx={{
                minHeight: 40,
                borderBottom: 1,
                borderColor: "divider",
                pb: 1,
              }}
            >
              <AutoAwesomeIcon color="primary" />
              <Box role="status" aria-live="polite">
                <Chip
                  size="small"
                  variant="outlined"
                  color={
                    executionState === "failed"
                      ? "error"
                      : executionState === "completed"
                      ? "success"
                      : "default"
                  }
                  label={`ReAct: ${
                    historyLoading
                      ? "履歴読込中"
                      : {
                          idle: "待機中",
                          running: "実行中",
                          completed: "完了",
                          failed: "失敗",
                        }[executionState]
                  }`}
                />
              </Box>
              {sending && (
                <CircularProgress size={18} aria-label="ReAct 実行中" />
              )}
            </Stack>
          )}
          {(sending || historyLoading) && (
            <LinearProgress aria-label={sending ? "応答待ち" : "履歴読込中"} />
          )}
          <List
            ref={messageListRef}
            sx={{
              flex: 1,
              overflowY: "auto",
              minHeight: isReAct ? 0 : 180,
              maxHeight: isReAct ? undefined : "60vh",
            }}
          >
            {visibleMessages.map((m) => (
              <ListItem
                key={m.id}
                alignItems="flex-start"
                sx={{
                  justifyContent: m.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <Stack
                  direction={m.role === "user" ? "row-reverse" : "row"}
                  spacing={2}
                  alignItems="flex-start"
                  sx={{ width: "100%" }}
                >
                  <Avatar>{m.role === "user" ? "U" : "A"}</Avatar>
                  <Paper
                    sx={{
                      p: 1.5,
                      maxWidth: "70%",
                      minWidth: 0,
                      overflowWrap: "anywhere",
                      bgcolor: m.role === "user" ? "primary.light" : "grey.100",
                    }}
                  >
                    <ListItemText
                      primary={m.content}
                      secondary={new Date(m.createdAt).toLocaleTimeString()}
                    />
                    {isReAct && m.role === "assistant" && m.usage && (
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="div"
                      >
                        入力 {m.usage.input_tokens ?? 0} / 出力{" "}
                        {m.usage.output_tokens ?? 0} tokens
                      </Typography>
                    )}
                    {m.citations?.length > 0 && (
                      <Box mt={1}>
                        <Typography variant="caption" color="text.secondary">
                          引用:
                        </Typography>
                        <Stack spacing={0.5} mt={0.5}>
                          {m.citations.map((c, idx) => (
                            <Typography
                              key={`${m.id}-citation-${idx}`}
                              variant="caption"
                              color="text.secondary"
                            >
                              ・{c.title || c.doc_id || `#${idx + 1}`} :{" "}
                              {c.snippet || "context"}
                            </Typography>
                          ))}
                        </Stack>
                      </Box>
                    )}
                  </Paper>
                </Stack>
              </ListItem>
            ))}
          </List>
          <Stack direction="row" spacing={2} sx={{ flexShrink: 0 }}>
            <TextField
              fullWidth
              label="メッセージ"
              slotProps={{ inputLabel: { shrink: true } }}
              placeholder="メッセージを入力..."
              value={input}
              disabled={sending || historyLoading}
              error={inputTooLong}
              helperText={isReAct ? `${inputLength} / 2000文字` : undefined}
              sx={{ minWidth: 0 }}
              onChange={(e) => setInput(e.target.value)}
              onCompositionStart={() => setIsComposing(true)}
              onCompositionEnd={() => setIsComposing(false)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !isComposing) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Tooltip title="送信">
              <span>
                <IconButton
                  aria-label="送信"
                  color="primary"
                  onClick={handleSend}
                  disabled={!canSend}
                  sx={{ width: 48, height: 48 }}
                >
                  <SendIcon />
                </IconButton>
              </span>
            </Tooltip>
          </Stack>
        </Box>
      </Container>
    </Box>
  );
}
