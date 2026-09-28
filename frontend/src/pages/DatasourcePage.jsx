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
  DialogTitle,
  FormControl,
  FormControlLabel,
  InputLabel,
  LinearProgress,
  Menu,
  MenuItem,
  Paper,
  Select,
  Stack,
  Switch,
  TextField,
  Tooltip,
  Typography,
  IconButton,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import ListAltRoundedIcon from "@mui/icons-material/ListAltRounded";
import { useNavigate } from "react-router-dom";
import { datasourceApi, getLLMs } from "../services/apiClient.js";

export default function DatasourcePage() {
  const navigate = useNavigate();
  const [datasources, setDatasources] = useState([]);
  const [llms, setLlms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [flashMessage, setFlashMessage] = useState(null);
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [formValues, setFormValues] = useState({
    name: "",
    description: "",
    llm: "",
    is_active: true,
  });
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [menuDatasource, setMenuDatasource] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const llmMap = useMemo(() => {
    const map = new Map();
    llms.forEach((llm) => map.set(llm.id, llm));
    return map;
  }, [llms]);

  useEffect(() => {
    loadPage();
  }, []);

  async function loadPage() {
    setLoading(true);
    setError(null);
    try {
      const [dsList, llmList] = await Promise.all([
        datasourceApi.list().catch(() => []),
        getLLMs(),
      ]);
      setDatasources(dsList || []);
      setLlms((llmList || []).filter((llm) => llm.is_active !== false));
    } catch (e) {
      setError(e.message || "データの取得に失敗しました");
    } finally {
      setLoading(false);
    }
  }

  const handleOpenCreate = () => {
    setFormValues({ name: "", description: "", llm: "", is_active: true });
    setFormError(null);
    setCreateDialogOpen(true);
  };

  const handleFormChange = (field, value) => {
    setFormValues((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreateSubmit = async (event) => {
    event.preventDefault();
    const name = formValues.name.trim();
    const llmId = Number(formValues.llm);
    if (!name || !llmId) {
      setFormError("名称とLLMを入力してください");
      return;
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await datasourceApi.create({
        name,
        description: formValues.description,
        llm: llmId,
        is_active: formValues.is_active,
      });
      setCreateDialogOpen(false);
      setFlashMessage("データソースを追加しました");
      await loadPage();
    } catch (e) {
      setFormError(e.message || "作成に失敗しました");
    } finally {
      setSubmitting(false);
    }
  };

  const openMenu = (event, datasource) => {
    setMenuAnchor(event.currentTarget);
    setMenuDatasource(datasource);
  };

  const closeMenu = () => {
    setMenuAnchor(null);
    setMenuDatasource(null);
  };

  const handleNavigateChunks = () => {
    if (!menuDatasource) return;
    navigate(`/datasources/${menuDatasource.id}/chunks`);
    closeMenu();
  };

  const handleDeleteRequest = () => {
    if (!menuDatasource) return;
    setDeleteTarget(menuDatasource);
    closeMenu();
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await datasourceApi.remove(deleteTarget.id);
      setFlashMessage("データソースを削除しました");
      await loadPage();
    } catch (e) {
      setError(e.message || "削除に失敗しました");
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
          alignItems="center"
          flexWrap="wrap"
          gap={2}
        >
          <Box>
            <Typography variant="h4" component="h1">
              データソース
            </Typography>
            <Typography color="text.secondary">
              RAG用のテキストチャンクを保持するデータソースを作成・管理します。
            </Typography>
          </Box>
          <Stack direction="row" spacing={1} alignItems="center">
            <Tooltip title="再読み込み">
              <span>
                <IconButton
                  onClick={loadPage}
                  color="primary"
                  disabled={loading}
                >
                  <RefreshIcon />
                </IconButton>
              </span>
            </Tooltip>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleOpenCreate}
            >
              追加
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
            flexWrap="wrap"
            gap={1}
          >
            <Typography variant="h6">登録済みデータソース</Typography>
            <Chip label={`${datasources.length}件`} variant="outlined" />
          </Box>
          {loading && <LinearProgress />}
          {!loading && datasources.length === 0 && (
            <Typography color="text.secondary">
              データソースがありません。「追加」ボタンから作成してください。
            </Typography>
          )}
          <Stack spacing={2} sx={{ flex: 1, overflowY: "auto" }}>
            {datasources.map((ds) => {
              const llm = llmMap.get(ds.llm);
              return (
                <Paper key={ds.id} variant="outlined" sx={{ p: 2 }}>
                  <Stack spacing={1.5}>
                    <Box
                      display="flex"
                      justifyContent="space-between"
                      alignItems="center"
                      flexWrap="wrap"
                      gap={1}
                    >
                      <Box>
                        <Typography variant="h6">{ds.name}</Typography>
                        <Stack direction="row" spacing={1} flexWrap="wrap">
                          {llm && (
                            <Chip
                              size="small"
                              label={`${llm.name} (${llm.provider})`}
                              variant="outlined"
                            />
                          )}
                          <Chip
                            size="small"
                            color={ds.is_active ? "success" : "default"}
                            label={ds.is_active ? "Active" : "Inactive"}
                          />
                        </Stack>
                      </Box>
                      <IconButton
                        size="small"
                        onClick={(event) => openMenu(event, ds)}
                      >
                        <MoreVertIcon />
                      </IconButton>
                    </Box>
                    {ds.description && (
                      <Typography color="text.secondary" variant="body2">
                        {ds.description}
                      </Typography>
                    )}
                  </Stack>
                </Paper>
              );
            })}
          </Stack>
        </Paper>
      </Stack>

      <Menu
        anchorEl={menuAnchor}
        open={Boolean(menuAnchor)}
        onClose={closeMenu}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
      >
        <MenuItem onClick={handleNavigateChunks}>
          <ListAltRoundedIcon fontSize="small" sx={{ mr: 1 }} />
          詳細
        </MenuItem>
        <MenuItem onClick={handleDeleteRequest}>
          <DeleteOutlineIcon fontSize="small" sx={{ mr: 1 }} />
          削除
        </MenuItem>
      </Menu>

      <Dialog
        open={createDialogOpen}
        onClose={() => (submitting ? null : setCreateDialogOpen(false))}
      >
        <DialogTitle>データソースを追加</DialogTitle>
        <DialogContent>
          <Stack
            component="form"
            spacing={2}
            sx={{ mt: 1 }}
            onSubmit={handleCreateSubmit}
          >
            <TextField
              label="名称"
              value={formValues.name}
              onChange={(e) => handleFormChange("name", e.target.value)}
              required
              fullWidth
            />
            <TextField
              label="説明"
              value={formValues.description}
              onChange={(e) => handleFormChange("description", e.target.value)}
              multiline
              minRows={2}
              fullWidth
            />
            <FormControl fullWidth required>
              <InputLabel id="llm-select-label">LLM</InputLabel>
              <Select
                labelId="llm-select-label"
                label="LLM"
                value={formValues.llm}
                onChange={(e) => handleFormChange("llm", e.target.value)}
              >
                {llms.map((llm) => (
                  <MenuItem key={llm.id} value={llm.id}>
                    {llm.name} ({llm.provider})
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControlLabel
              control={
                <Switch
                  checked={formValues.is_active}
                  onChange={(e) =>
                    handleFormChange("is_active", e.target.checked)
                  }
                />
              }
              label="Active"
            />
            {formError && <Alert severity="error">{formError}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => setCreateDialogOpen(false)}
            disabled={submitting}
          >
            キャンセル
          </Button>
          <Button
            onClick={handleCreateSubmit}
            variant="contained"
            disabled={submitting}
          >
            {submitting ? "作成中..." : "作成"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(deleteTarget)}
        onClose={() => (deleting ? null : setDeleteTarget(null))}
      >
        <DialogTitle>削除の確認</DialogTitle>
        <DialogContent>
          <Typography>
            {deleteTarget ? `${deleteTarget.name} を削除しますか？` : ""}
          </Typography>
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
