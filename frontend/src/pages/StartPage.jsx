import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";

export default function StartPage() {
  const navigate = useNavigate();

  return (
    <Container maxWidth="sm" className="center-page">
      <Box>
        <Stack spacing={3} alignItems="center">
          <Typography variant="h3" component="h1" align="center">
            Simple Chat
          </Typography>
          <Typography color="text.secondary" align="center">
            認証は後日追加予定です。Startを押してメニューへ。
          </Typography>
          <Button
            variant="contained"
            size="large"
            onClick={() => navigate("/menu")}
          >
            Start
          </Button>
        </Stack>
      </Box>
    </Container>
  );
}
