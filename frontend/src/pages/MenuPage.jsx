import { Fragment } from "react";
import {
  Container,
  Divider,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Stack,
  Typography,
} from "@mui/material";
import ChatBubbleOutlineRoundedIcon from "@mui/icons-material/ChatBubbleOutlineRounded";
import AutoAwesomeRoundedIcon from "@mui/icons-material/AutoAwesomeRounded";
import CloudUploadRoundedIcon from "@mui/icons-material/CloudUploadRounded";
import StorageRoundedIcon from "@mui/icons-material/StorageRounded";
import { useNavigate } from "react-router-dom";

const FEATURES = [
  {
    title: "シンプルチャット",
    description:
      "既存のLLMチャット体験。モデル選択とセッション管理が行えます。",
    path: "/simple-chat",
    icon: ChatBubbleOutlineRoundedIcon,
    action: "開く",
  },
  {
    title: "エージェント",
    description:
      "Django Adminで定義したエージェントを一覧・作成し、RAGチャットを開始できます。",
    path: "/agent",
    icon: AutoAwesomeRoundedIcon,
    action: "開く",
  },
  {
    title: "データソース管理",
    description:
      "RAG用のデータソースとチャンクを作成・削除し、エージェントで参照できるようにします。",
    path: "/datasources",
    icon: StorageRoundedIcon,
    action: "管理する",
  },
  {
    title: "データ登録",
    description:
      "ドキュメントを取り込み、検索可能な知識ベースを構築するUIを開発予定です。",
    path: "/data-registration",
    icon: CloudUploadRoundedIcon,
    action: "モックを見る",
  },
];

export default function MenuPage() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="md" className="center-page">
      <Stack spacing={3}>
        <Typography variant="h4" component="h1">
          機能メニュー
        </Typography>
        <Typography color="text.secondary">
          利用したい機能を選択してください。準備中の機能にはモック画面を用意しています。
        </Typography>

        <List
          sx={{
            borderRadius: 2,
            border: 1,
            borderColor: "divider",
            bgcolor: "background.paper",
            boxShadow: 1,
          }}
        >
          {FEATURES.map((feature, index) => {
            const IconComponent = feature.icon;
            const showDivider = index < FEATURES.length - 1;

            return (
              <Fragment key={feature.title}>
                <ListItemButton
                  onClick={() => navigate(feature.path)}
                  alignItems="flex-start"
                >
                  <ListItemIcon sx={{ minWidth: 48 }}>
                    <IconComponent color="primary" />
                  </ListItemIcon>
                  <ListItemText
                    primary={feature.title}
                    secondary={feature.description}
                    primaryTypographyProps={{ variant: "h6" }}
                    secondaryTypographyProps={{ color: "text.secondary" }}
                  />
                  <Typography variant="body2" color="text.secondary">
                    {feature.action}
                  </Typography>
                </ListItemButton>
                {showDivider && <Divider component="li" />}
              </Fragment>
            );
          })}
        </List>
      </Stack>
    </Container>
  );
}
