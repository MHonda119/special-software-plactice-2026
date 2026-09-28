import { useEffect, useMemo, useRef, useState } from "react";
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Container,
  Paper,
  Stack,
  TextField,
  Button,
  Box,
  List,
  ListItem,
  ListItemText,
  Avatar,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SendIcon from "@mui/icons-material/Send";
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
  const [input, setInput] = useState("");
  const [isComposing, setIsComposing] = useState(false);
  const listEndRef = useRef(null);

  const visibleMessages = useMemo(
    () => messages.filter((m) => m.role !== "system"),
    [messages],
  );

  useEffect(() => {
    if (!activeSessionId) {
      setMessages([]);
      return;
    }
    (async () => {
      try {
        const ms = await apiGetMessages(activeSessionId);
        // Map backend fields to UI as needed
        const mapped = ms.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          createdAt: m.created_at || m.createdAt || new Date().toISOString(),
          citations: m.metadata?.citations,
        }));
        setMessages(mapped);
        // Derive title from first user message
        const firstUser = mapped.find((x) => x.role === "user");
        setSessionTitle(
          agentName ||
            (firstUser ? firstUser.content.slice(0, 20) : "New Chat"),
        );
      } catch {
        setMessages([]);
        setSessionTitle(agentName || "New Chat");
      }
    })();
  }, [activeSessionId, agentName]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleMessages]);

  const canSend = useMemo(() => {
    if (!input.trim()) return false;
    if (isAgentChat) return true;
    return Boolean(activeSessionId);
  }, [input, isAgentChat, activeSessionId]);

  const handleSend = async () => {
    if (!canSend) return;
    const text = input.trim();
    setInput("");
    try {
      // Optimistic append user message
      const userMsg = {
        id: `temp-${Date.now()}`,
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
        };
        setMessages((prev) => [...prev, assistantMsg]);
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
      if (!sessionTitle) setSessionTitle(text.slice(0, 20));
    } catch (e) {
      alert(`送信に失敗しました: ${e.message}`);
    }
  };

  return (
    <Box className="chat-shell">
      <AppBar position="static">
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={() => navigate("/menu")}
          >
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" sx={{ ml: 1 }}>
            {sessionTitle || "New Chat"}
          </Typography>
        </Toolbar>
      </AppBar>
      <Container
        maxWidth="md"
        className="chat-content"
        style={{ paddingTop: 16, paddingBottom: 16 }}
      >
        <Paper
          sx={{ width: "100%", display: "flex", flexDirection: "column", p: 2 }}
        >
          <List sx={{ flex: 1, overflowY: "auto" }}>
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
                      bgcolor: m.role === "user" ? "primary.light" : "grey.100",
                    }}
                  >
                    <ListItemText
                      primary={m.content}
                      secondary={new Date(m.createdAt).toLocaleTimeString()}
                    />
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
            <div ref={listEndRef} />
          </List>
          <Stack direction="row" spacing={2}>
            <TextField
              fullWidth
              placeholder="メッセージを入力..."
              value={input}
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
            <Button
              variant="contained"
              endIcon={<SendIcon />}
              onClick={handleSend}
              disabled={!canSend}
            >
              送信
            </Button>
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
