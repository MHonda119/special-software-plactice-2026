import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Container,
  Chip,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import SaveIcon from "@mui/icons-material/Save";
import { useNavigate, useParams } from "react-router-dom";
import { agentApi, datasourceApi, getLLMs } from "../services/apiClient.js";
import {
  AGENT_USECASE_TYPES,
  findUsecaseMeta,
} from "../constants/agentUsecases.js";

const DEFAULT_FORM = {
  name: "",
  usecaseType: "RAG_CHAT",
  llmId: "",
  systemPrompt: "",
  datasourceIds: [],
  temperature: "0.2",
  topK: "3",
  citationChars: "120",
  embedModel: "",
};

function mapAgentToForm(agent) {
  const config = agent.config || {};
  return {
    name: agent.name || "",
    usecaseType: agent.usecase_type || "RAG_CHAT",
    llmId: agent.llm ? String(agent.llm) : "",
    systemPrompt: agent.system_prompt || "",
    datasourceIds: (config.datasource_ids || []).map((id) => String(id)),
    temperature:
      config.temperature !== undefined ? String(config.temperature) : "0.2",
    topK: config.top_k !== undefined ? String(config.top_k) : "3",
    citationChars:
      config.citation_snippet_chars !== undefined
        ? String(config.citation_snippet_chars)
        : "120",
    embedModel:
      config.embed_model !== undefined ? String(config.embed_model) : "",
  };
}

export default function AgentFormPage() {
  const navigate = useNavigate();
  const { agentId } = useParams();
  const isEdit = Boolean(agentId);

  const [form, setForm] = useState(() => ({ ...DEFAULT_FORM }));
  const [llms, setLlms] = useState([]);
  const [datasources, setDatasources] = useState([]);
  const [originalAgent, setOriginalAgent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const requiresDatasource = useMemo(() => {
    const meta = findUsecaseMeta(form.usecaseType);
    return meta?.requiresDatasources;
  }, [form.usecaseType]);

  const llmMap = useMemo(() => {
    const map = new Map();
    llms.forEach((llm) => map.set(String(llm.id), llm));
    return map;
  }, [llms]);

  const datasourceMap = useMemo(() => {
    const map = new Map();
    datasources.forEach((ds) => map.set(String(ds.id), ds));
    return map;
  }, [datasources]);

  const detectedEmbedModels = useMemo(() => {
    if (form.usecaseType !== "RAG_CHAT") return [];
    const collector = new Map();
    form.datasourceIds.forEach((dsId) => {
      const ds = datasourceMap.get(String(dsId));
      if (!ds) return;
      const llm = llmMap.get(String(ds.llm));
      if (!llm) return;
      const key = `${llm.provider}:${llm.model}`;
      if (!collector.has(key)) {
        collector.set(key, {
          key,
          model: llm.model,
          provider: llm.provider,
          label: `${llm.name} (${llm.provider}:${llm.model})`,
          datasourceNames: new Set(),
        });
      }
      collector.get(key).datasourceNames.add(ds.name || `ID ${ds.id}`);
    });
    return Array.from(collector.values()).map((entry) => ({
      ...entry,
      datasourceNames: Array.from(entry.datasourceNames),
    }));
  }, [form.datasourceIds, datasourceMap, llmMap, form.usecaseType]);

  const autoEmbedModel = useMemo(() => {
    if (detectedEmbedModels.length === 1) {
      return detectedEmbedModels[0];
    }
    return null;
  }, [detectedEmbedModels]);

  useEffect(() => {
    if (form.usecaseType !== "RAG_CHAT") return;
    if (!autoEmbedModel) return;
    if (form.embedModel) return;
    setForm((prev) => {
      if (prev.embedModel) return prev;
      return { ...prev, embedModel: autoEmbedModel.model };
    });
  }, [autoEmbedModel, form.usecaseType, form.embedModel]);

  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [llmList, datasourceList] = await Promise.all([
        getLLMs(),
        datasourceApi.list().catch(() => []),
      ]);
      setLlms(llmList.filter((l) => l.is_active !== false));
      setDatasources(datasourceList.filter((d) => d.is_active !== false));

      if (isEdit && agentId) {
        const detail = await agentApi.retrieve(agentId);
        setOriginalAgent(detail);
        setForm(mapAgentToForm(detail));
      } else {
        setOriginalAgent(null);
        setForm({ ...DEFAULT_FORM });
      }
    } catch (e) {
      setError(e.message || "フォームの読み込みに失敗しました");
    } finally {
      setLoading(false);
    }
  }, [agentId, isEdit]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const handleChange = (field) => (event) => {
    const value = event.target.value;
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const canSubmit = useMemo(() => {
    if (loading || saving) return false;
    if (!form.name.trim()) return false;
    if (!form.llmId) return false;
    if (requiresDatasource && form.datasourceIds.length === 0) return false;
    if (form.usecaseType === "RAG_CHAT" && !form.embedModel.trim())
      return false;
    return true;
  }, [form, requiresDatasource, loading, saving]);

  const buildConfigPayload = () => {
    const base = { ...(originalAgent?.config || {}) };
    base.temperature = Number(form.temperature || 0.2);

    if (form.usecaseType === "RAG_CHAT") {
      if (form.topK) base.top_k = Number(form.topK);
      if (form.citationChars)
        base.citation_snippet_chars = Number(form.citationChars);
      base.datasource_ids = form.datasourceIds.map((id) => Number(id));
      if (form.embedModel?.trim()) {
        base.embed_model = form.embedModel.trim();
      } else {
        delete base.embed_model;
      }
    } else {
      delete base.top_k;
      delete base.citation_snippet_chars;
      delete base.datasource_ids;
      delete base.embed_model;
    }
    return base;
  };

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSaving(true);
    setError(null);
    const payload = {
      name: form.name.trim(),
      usecase_type: form.usecaseType,
      llm: Number(form.llmId),
      system_prompt: form.systemPrompt.trim() || undefined,
      config: buildConfigPayload(),
      is_active: originalAgent?.is_active ?? true,
    };
    try {
      if (isEdit && agentId) {
        await agentApi.patch(agentId, payload);
        navigate("/agent", {
          replace: true,
          state: { message: "エージェントを更新しました" },
        });
      } else {
        await agentApi.create(payload);
        navigate("/agent", {
          replace: true,
          state: { message: "エージェントを作成しました" },
        });
      }
    } catch (e) {
      setError(e.message || "保存に失敗しました");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Container maxWidth="md" className="center-page">
      <Stack spacing={3}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          flexWrap="wrap"
          gap={2}
        >
          <Box>
            <Typography variant="h4" component="h1">
              {isEdit ? "Agent編集" : "Agent作成"}
            </Typography>
            <Typography color="text.secondary">
              LLMやデータソースを組み合わせてユースケースを定義します。必要事項を入力し保存してください。
            </Typography>
          </Box>
          <Button
            startIcon={<ArrowBackIcon />}
            onClick={() => navigate("/agent")}
          >
            一覧へ戻る
          </Button>
        </Stack>

        {error && <Alert severity="error">{error}</Alert>}

        <Paper sx={{ p: 3 }}>
          {loading ? (
            <LinearProgress />
          ) : (
            <Stack spacing={2}>
              <TextField
                label="エージェント名"
                value={form.name}
                onChange={handleChange("name")}
                required
              />
              <FormControl fullWidth>
                <InputLabel id="usecase-type-label">ユースケース</InputLabel>
                <Select
                  labelId="usecase-type-label"
                  label="ユースケース"
                  value={form.usecaseType}
                  onChange={handleChange("usecaseType")}
                >
                  {AGENT_USECASE_TYPES.map((type) => (
                    <MenuItem key={type.value} value={type.value}>
                      {type.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl fullWidth>
                <InputLabel id="llm-select-label">LLM</InputLabel>
                <Select
                  labelId="llm-select-label"
                  label="LLM"
                  value={form.llmId}
                  onChange={handleChange("llmId")}
                >
                  {llms.map((llm) => (
                    <MenuItem key={llm.id} value={llm.id}>
                      {`${llm.name} (${llm.provider}:${llm.model})`}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <TextField
                label="システムプロンプト"
                multiline
                minRows={3}
                value={form.systemPrompt}
                onChange={handleChange("systemPrompt")}
                placeholder="エージェントの人格や方針を記入"
              />
              {requiresDatasource && (
                <FormControl fullWidth>
                  <InputLabel id="datasource-select-label">
                    データソース
                  </InputLabel>
                  <Select
                    labelId="datasource-select-label"
                    label="データソース"
                    multiple
                    value={form.datasourceIds}
                    onChange={handleChange("datasourceIds")}
                    renderValue={(selected) =>
                      selected
                        .map(
                          (id) =>
                            datasources.find(
                              (ds) => String(ds.id) === String(id),
                            )?.name || id,
                        )
                        .join(", ")
                    }
                  >
                    {datasources.map((ds) => (
                      <MenuItem key={ds.id} value={String(ds.id)}>
                        {ds.name}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              )}
              {form.usecaseType === "RAG_CHAT" && (
                <Stack spacing={1}>
                  <TextField
                    label="埋め込みモデル (embed_model)"
                    value={form.embedModel}
                    onChange={handleChange("embedModel")}
                    required
                    placeholder="例: text-embedding-3-small"
                    helperText="データソース登録時に使用した埋め込みモデルを指定してください"
                  />
                  {detectedEmbedModels.length > 0 && (
                    <Stack direction="row" spacing={1} flexWrap="wrap">
                      {detectedEmbedModels.map((candidate) => (
                        <Chip
                          key={candidate.key}
                          label={`${candidate.model} (${candidate.provider})`}
                          color={
                            form.embedModel === candidate.model
                              ? "primary"
                              : "default"
                          }
                          variant={
                            form.embedModel === candidate.model
                              ? "filled"
                              : "outlined"
                          }
                          size="small"
                          onClick={() =>
                            setForm((prev) => ({
                              ...prev,
                              embedModel: candidate.model,
                            }))
                          }
                        />
                      ))}
                    </Stack>
                  )}
                  {autoEmbedModel && (
                    <Typography variant="body2" color="text.secondary">
                      選択されたデータソースから推奨: {autoEmbedModel.label}
                    </Typography>
                  )}
                  {detectedEmbedModels.length > 1 && (
                    <Alert severity="warning">
                      データソース間で埋め込みモデルが混在しています。使用するモデルを明示的に選択してください。
                    </Alert>
                  )}
                </Stack>
              )}
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <TextField
                  label="temperature"
                  value={form.temperature}
                  onChange={handleChange("temperature")}
                  type="number"
                  inputProps={{ step: 0.1 }}
                  fullWidth
                />
                <TextField
                  label="top_k"
                  value={form.topK}
                  onChange={handleChange("topK")}
                  type="number"
                  inputProps={{ min: 1 }}
                  disabled={form.usecaseType !== "RAG_CHAT"}
                  fullWidth
                />
                <TextField
                  label="citation chars"
                  value={form.citationChars}
                  onChange={handleChange("citationChars")}
                  type="number"
                  inputProps={{ min: 20 }}
                  disabled={form.usecaseType !== "RAG_CHAT"}
                  fullWidth
                />
              </Stack>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button onClick={() => navigate("/agent")}>キャンセル</Button>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  disabled={!canSubmit}
                  onClick={handleSubmit}
                >
                  {isEdit ? "更新する" : "作成する"}
                </Button>
              </Stack>
            </Stack>
          )}
        </Paper>
      </Stack>
    </Container>
  );
}
