export const AGENT_USECASE_TYPES = [
  {
    value: "RAG_CHAT",
    label: "RAGチャット",
    description:
      "ドキュメント検索 (RAG) を行ってから応答する高度なチャット。データソース選択を予め設定する必要があります。",
    requiresDatasources: true,
  },
  {
    value: "BASIC_CHAT",
    label: "ベーシックチャット",
    description:
      "単純なLLMチャット。システムプロンプトやLLMの生成設定 (temperature など) だけを調整します。",
    requiresDatasources: false,
  },
];

export function findUsecaseMeta(type) {
  return AGENT_USECASE_TYPES.find((item) => item.value === type);
}
