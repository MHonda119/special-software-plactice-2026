import {
  Container,
  Paper,
  Stack,
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  Button,
} from "@mui/material";

export default function DataRegistrationPage() {
  return (
    <Container maxWidth="md" className="center-page">
      <Stack spacing={3}>
        <Box>
          <Typography variant="h4" component="h1">
            データ登録 (準備中)
          </Typography>
          <Typography color="text.secondary">
            ドキュメントをアップロードしてRAG用の知識ベースを作成する機能を開発中です。
          </Typography>
        </Box>

        <Paper sx={{ p: 3 }}>
          <Stack spacing={2}>
            <Typography variant="h6">想定フロー</Typography>
            <List>
              {[
                "データソースの作成",
                "ファイル or テキストの登録",
                "埋め込み生成とインデックス化",
              ].map((step) => (
                <ListItem key={step}>
                  <ListItemText primary={step} />
                </ListItem>
              ))}
            </List>
            <Typography color="text.secondary">
              API設計とセキュリティ要件を整理中のため、しばらくお待ちください。
            </Typography>
            <Box>
              <Button variant="outlined" disabled>
                Coming Soon
              </Button>
            </Box>
          </Stack>
        </Paper>
      </Stack>
    </Container>
  );
}
