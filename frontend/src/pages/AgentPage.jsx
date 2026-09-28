import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  LinearProgress,
  Menu,
  MenuItem,
  Paper,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import EditRoundedIcon from "@mui/icons-material/EditRounded";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { useLocation, useNavigate } from "react-router-dom";
import { agentApi, datasourceApi, getLLMs } from "../services/apiClient.js";
import { findUsecaseMeta } from "../constants/agentUsecases.js";

export default function AgentPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [agents, setAgents] = useState([]);
  const [llms, setLlms] = useState([]);
  const [datasources, setDatasources] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [menuAgent, setMenuAgent] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [flashMessage, setFlashMessage] = useState(location.state?.message);

  const llmMap = useMemo(() => {
    const map = new Map();
    llms.forEach((l) => map.set(l.id, l));
    return map;
  }, [llms]);

  const datasourceMap = useMemo(() => {
    const map = new Map();
    datasources.forEach((d) => map.set(d.id, d));
    return map;
  }, [datasources]);

  useEffect(() => {
    loadPage();
  }, []);

  useEffect(() => {
    if (location.state?.message) {
      setFlashMessage(location.state.message);
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location, navigate]);

  async function loadPage() {
    setLoading(true);
    setError(null);
    try {
      const [agentList, llmList, datasourceList] = await Promise.all([
        agentApi.list(),
        getLLMs(),
        datasourceApi.list().catch(() => []),
      ]);
      setAgents(agentList);
      setLlms(llmList.filter((l) => l.is_active !== false));
      setDatasources(datasourceList.filter((d) => d.is_active !== false));
    } catch (e) {
      setError(e.message || "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  const handleExecute = (agent) => {
    const query = new URLSearchParams({
      agentId: agent.id,
      agentName: agent.name,
      usecaseType: agent.usecase_type,
    });
    navigate(`/chat?${query.toString()}`);
  };

  const openMenuForAgent = (event, agent) => {
    setMenuAnchor(event.currentTarget);
    setMenuAgent(agent);
  };

  const closeMenu = () => {
    setMenuAnchor(null);
    setMenuAgent(null);
  };

  const handleEdit = () => {
    if (!menuAgent) return;
    navigate(`/agent/${menuAgent.id}/edit`);
    closeMenu();
  };

  const handleDeleteRequest = () => {
    if (!menuAgent) return;
    setDeleteTarget(menuAgent);
    closeMenu();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await agentApi.remove(deleteTarget.id);
      setFlashMessage("エージェントを削除しました");
      await loadPage();
    } catch (e) {
      setError(e.message || "エージェントの削除に失敗しました");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  return (
    <Container maxWidth="lg" className="center-page">
      <Stack spacing={3}>
        <Box
          display="flex"
          justifyContent="space-between"
          flexWrap="wrap"
          gap={2}
        >
          <Box>
            <Typography variant="h4" component="h1">
              エージェント
            </Typography>
            <Typography color="text.secondary">
              Django
              Adminで定義済みのLLMとデータソースを組み合わせ、RAGや高度なチャット体験を開始できます。
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="最新の状態に更新">
              <span>
                <IconButton
                  color="primary"
                  onClick={loadPage}
                  disabled={loading}
                >
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Button
              startIcon={<AddIcon />}
              variant="contained"
              onClick={() => navigate("/agent/new")}
            >
              Agent作成
            </Button>
          </Stack>
        </Box>

        {flashMessage && (
          <Alert severity="success" onClose={() => setFlashMessage(null)}>
            {flashMessage}
          </Alert>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        <Paper
          sx={{
            p: 3,
            minHeight: 400,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
            flexWrap="wrap"
            gap={1}
          >
            <Typography variant="h6">登録済みエージェント</Typography>
            <Chip
              label={`${agents.length}件`}
              color="primary"
              variant="outlined"
            />
          </Box>
          {loading && <LinearProgress />}
          {!loading && agents.length === 0 && (
            <Typography color="text.secondary">
              エージェントがまだありません。「Agent作成」ボタンから登録してください。
            </Typography>
          )}
          <Stack spacing={2} sx={{ flex: 1, overflowY: "auto" }}>
            {agents.map((agent) => {
              const llm = llmMap.get(agent.llm);
              const usecase = findUsecaseMeta(agent.usecase_type);
              const datasourceNames = (agent.config?.datasource_ids || [])
                .map((id) => datasourceMap.get(id)?.name || `ID:${id}`)
                .join(", ");
              return (
                <Paper key={agent.id} variant="outlined" sx={{ p: 2 }}>
                  <Stack spacing={1.2}>
                    <Box
                      display="flex"
                      justifyContent="space-between"
                      alignItems="center"
                      flexWrap="wrap"
                      gap={1}
                    >
                      <Stack spacing={0.5}>
                        <Typography variant="h6">{agent.name}</Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap">
                          <Chip
                            label={usecase?.label || agent.usecase_type}
                            color={
                              agent.usecase_type === "RAG_CHAT"
                                ? "secondary"
                                : "default"
                            }
                            size="small"
                          />
                          {llm && (
                            <Chip
                              label={`${llm.name} (${llm.provider}:${llm.model})`}
                              variant="outlined"
                              size="small"
                            />
                          )}
                          <Chip
                            label={agent.is_active ? "Active" : "Inactive"}
                            color={agent.is_active ? "success" : "default"}
                            size="small"
                          />
                        </Stack>
                      </Stack>
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Button
                          variant="contained"
                          startIcon={<PlayArrowRoundedIcon />}
                          onClick={() => handleExecute(agent)}
                        >
                          チャット開始
                        </Button>
                        <IconButton
                          size="small"
                          color="inherit"
                          aria-label="more"
                          onClick={(event) => openMenuForAgent(event, agent)}
                        >
                          <MoreVertIcon />
                        </IconButton>
                      </Stack>
                    </Box>
                    {agent.system_prompt && (
                      <Typography color="text.secondary" variant="body2">
                        {agent.system_prompt}
                      </Typography>
                    )}
                    {agent.config && Object.keys(agent.config).length > 0 && (
                      <Box>
                        <Typography variant="subtitle2" color="text.secondary">
                          設定
                        </Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap">
                          {Object.entries(agent.config).map(([key, value]) => (
                            <Chip
                              key={`${agent.id}-${key}`}
                              label={`${key}: ${
                                Array.isArray(value) ? value.join(",") : value
                              }`}
                              size="small"
                            />
                          ))}
                        </Stack>
                      </Box>
                    )}
                    {agent.usecase_type === "RAG_CHAT" && datasourceNames && (
                      <Typography variant="body2" color="text.secondary">
                        参照データ: {datasourceNames}
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        </Paper>

        <Box>
          <Typography variant="h6">使い方</Typography>
          <Typography color="text.secondary">
            Agentの作成や編集は専用画面で行い、登録済みエージェントは本一覧からチャット実行や管理メニューで操作できます。
          </Typography>
        </Box>
      </Stack>

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <MenuItem onClick={handleEdit}>
          <EditRoundedIcon fontSize="small" sx={{ mr: 1 }} /> 編集
        </MenuItem>
        <MenuItem onClick={handleDeleteRequest}>
          <DeleteOutlineIcon fontSize="small" sx={{ mr: 1 }} /> 削除
        </MenuItem>
      </Menu>

      <Dialog
        open={Boolean(deleteTarget)}
        onClose={() => (deleting ? null : setDeleteTarget(null))}
      >
        <DialogTitle>エージェントを削除しますか?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {deleteTarget
              ? `${deleteTarget.name} を削除すると復元できません。`
              : ""}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>
            キャンセル
          </Button>
          <Button
            color="error"
            onClick={handleDeleteConfirm}
            disabled={deleting}
          >
            {deleting ? "削除中..." : "削除"}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
