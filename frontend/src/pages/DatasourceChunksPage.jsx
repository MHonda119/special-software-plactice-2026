import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  Alert,
  Box,
  Button,
  Chip,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { datasourceApi, getLLMs } from "../services/apiClient.js";

const DEFAULT_LIMIT = 50;

export default function DatasourceChunksPage() {
  const { datasourceId } = useParams();
  const navigate = useNavigate();
  const [datasource, setDatasource] = useState(null);
  const [llms, setLlms] = useState([]);
  const [chunks, setChunks] = useState([]);
  const [meta, setMeta] = useState({
    limit: DEFAULT_LIMIT,
    offset: 0,
    count: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flashMessage, setFlashMessage] = useState(null);
  const [chunkDialogOpen, setChunkDialogOpen] = useState(false);
  const [chunkForm, setChunkForm] = useState({ title: "", chunk_text: "" });
  const [chunkError, setChunkError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const llmMap = useMemo(() => {
    const map = new Map();
    llms.forEach((llm) => map.set(llm.id, llm));
    return map;
  }, [llms]);

  const loadData = useCallback(async () => {
    if (!datasourceId) return;
    setLoading(true);
    setError(null);
    try {
      const [ds, chunkResponse, llmList] = await Promise.all([
        datasourceApi.retrieve(datasourceId),
        datasourceApi.listChunks(datasourceId, { limit: DEFAULT_LIMIT }),
        getLLMs(),
      ]);
      setDatasource(ds);
      setChunks(chunkResponse?.chunks || []);
      setMeta({
        limit: chunkResponse?.limit ?? DEFAULT_LIMIT,
        offset: chunkResponse?.offset ?? 0,
        count: chunkResponse?.count ?? 0,
      });
      setLlms((llmList || []).filter((llm) => llm.is_active !== false));
    } catch (e) {
      setError(e.message || "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }, [datasourceId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleChunkFormChange = (field, value) => {
    setChunkForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleAddChunk = async (event) => {
    event?.preventDefault();
    if (!datasourceId) return;
    const title = chunkForm.title.trim();
    const text = chunkForm.chunk_text.trim();
    if (!title || !text) {
      setChunkError("タイトルとテキストを入力してください");
      return;
    }
    setSubmitting(true);
    setChunkError(null);
    try {
      await datasourceApi.addChunk(datasourceId, {
        title,
        chunk_text: text,
      });
      setFlashMessage("チャンクを追加しました");
      setChunkDialogOpen(false);
      setChunkForm({ title: "", chunk_text: "" });
      await loadData();
    } catch (e) {
      setChunkError(e.message || "追加に失敗しました");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteChunk = async () => {
    if (!datasourceId || !deleteTarget) return;
    setDeleting(true);
    try {
      await datasourceApi.deleteChunk(datasourceId, deleteTarget.chunk_id);
      setFlashMessage("チャンクを削除しました");
      await loadData();
    } catch (e) {
      setError(e.message || "削除に失敗しました");
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
  };

  const llm = datasource ? llmMap.get(datasource.llm) : null;

  return (
    <Container maxWidth="lg" className="center-page">
      <Stack spacing={3}>
        <Box
          display="flex"
          justifyContent="space-between"
          flexWrap="wrap"
          gap={2}
        >
          <Stack spacing={1}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)}>
              戻る
            </Button>
            <Typography variant="h4" component="h1">
              チャンク一覧
            </Typography>
            <Typography color="text.secondary">
              {datasource
                ? `${datasource.name} のチャンクを管理します`
                : "読み込み中..."}
            </Typography>
            {datasource && (
              <Stack direction="row" spacing={1} flexWrap="wrap">
                <Chip label={`ID: ${datasource.id}`} size="small" />
                {llm && (
                  <Chip
                    label={`${llm.name} (${llm.provider})`}
                    size="small"
                    variant="outlined"
                  />
                )}
                <Chip
                  label={datasource.is_active ? "Active" : "Inactive"}
                  size="small"
                  color={datasource.is_active ? "success" : "default"}
                />
              </Stack>
            )}
          </Stack>
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="再読み込み">
              <span>
                <IconButton
                  color="primary"
                  onClick={loadData}
                  disabled={loading}
                >
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setChunkDialogOpen(true)}
              disabled={!datasource}
            >
              チャンク追加
            </Button>
          </Stack>
        </Box>

        {flashMessage && (
          <Alert severity="success" onClose={() => setFlashMessage(null)}>
            {flashMessage}
          </Alert>
        )}
        {error && <Alert severity="error">{error}</Alert>}

        {datasource && datasource.description && (
          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" color="text.secondary">
              説明
            </Typography>
            <Typography>{datasource.description}</Typography>
          </Paper>
        )}

        <Paper
          sx={{
            p: 3,
            minHeight: 360,
            display: "flex",
            flexDirection: "column",
            gap: 2,
          }}
        >
          <Box
            display="flex"
            justifyContent="space-between"
            alignItems="center"
          >
            <Typography variant="h6">チャンク</Typography>
            <Chip
              label={`${chunks.length}件 / limit ${meta.limit}`}
              variant="outlined"
            />
          </Box>
          {loading && <LinearProgress />}
          {!loading && chunks.length === 0 && (
            <Typography color="text.secondary">
              チャンクがまだ登録されていません。
            </Typography>
          )}
          <Stack spacing={2} sx={{ flex: 1, overflowY: "auto" }}>
            {chunks.map((chunk) => (
              <Paper key={chunk.chunk_id} variant="outlined" sx={{ p: 2 }}>
                <Stack spacing={1.2}>
                  <Box
                    display="flex"
                    justifyContent="space-between"
                    flexWrap="wrap"
                    gap={1}
                  >
                    <Stack spacing={0.5}>
                      <Typography variant="subtitle1">
                        {chunk.title || "(無題)"}
                      </Typography>
                      <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ fontFamily: "monospace" }}
                      >
                        {chunk.chunk_id}
                      </Typography>
                    </Stack>
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Chip label={`${chunk.text_length} chars`} size="small" />
                      <IconButton
                        size="small"
                        color="error"
                        onClick={() => setDeleteTarget(chunk)}
                      >
                        <DeleteOutlineIcon />
                      </IconButton>
                    </Stack>
                  </Box>
                </Stack>
              </Paper>
            ))}
          </Stack>
        </Paper>
      </Stack>

      <Dialog
        open={chunkDialogOpen}
        onClose={() => (submitting ? null : setChunkDialogOpen(false))}
        fullWidth
        maxWidth="sm"
      >
        <DialogTitle>チャンクを追加</DialogTitle>
        <DialogContent>
          <Stack
            component="form"
            spacing={2}
            sx={{ mt: 1 }}
            onSubmit={handleAddChunk}
          >
            <TextField
              label="タイトル"
              value={chunkForm.title}
              onChange={(e) => handleChunkFormChange("title", e.target.value)}
              required
              fullWidth
            />
            <TextField
              label="テキスト"
              value={chunkForm.chunk_text}
              onChange={(e) =>
                handleChunkFormChange("chunk_text", e.target.value)
              }
              required
              fullWidth
              multiline
              minRows={4}
            />
            {chunkError && <Alert severity="error">{chunkError}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setChunkDialogOpen(false)}
            disabled={submitting}
          >
            キャンセル
          </Button>
          <Button
            variant="contained"
            onClick={handleAddChunk}
            disabled={submitting}
          >
            {submitting ? "追加中..." : "追加"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(deleteTarget)}
        onClose={() => (deleting ? null : setDeleteTarget(null))}
      >
        <DialogTitle>チャンクの削除</DialogTitle>
        <DialogContent>
          <Typography>
            {deleteTarget
              ? `${
                  deleteTarget.title || deleteTarget.chunk_id
                } を削除しますか？`
              : ""}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)} disabled={deleting}>
            キャンセル
          </Button>
          <Button color="error" onClick={handleDeleteChunk} disabled={deleting}>
            {deleting ? "削除中..." : "削除"}
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
}
