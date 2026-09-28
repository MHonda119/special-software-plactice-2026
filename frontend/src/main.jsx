import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./app.css";
import StartPage from "./pages/StartPage.jsx";
import MenuPage from "./pages/MenuPage.jsx";
import SimpleChatSetupPage from "./pages/SimpleChatSetupPage.jsx";
import ChatPage from "./pages/ChatPage.jsx";
import AgentPage from "./pages/AgentPage.jsx";
import AgentFormPage from "./pages/AgentFormPage.jsx";
import DataRegistrationPage from "./pages/DataRegistrationPage.jsx";
import DatasourcePage from "./pages/DatasourcePage.jsx";
import DatasourceChunksPage from "./pages/DatasourceChunksPage.jsx";

const router = createBrowserRouter([
  { path: "/", element: <StartPage /> },
  { path: "/menu", element: <MenuPage /> },
  { path: "/simple-chat", element: <SimpleChatSetupPage /> },
  { path: "/agent", element: <AgentPage /> },
  { path: "/agent/new", element: <AgentFormPage /> },
  { path: "/agent/:agentId/edit", element: <AgentFormPage /> },
  { path: "/datasources", element: <DatasourcePage /> },
  {
    path: "/datasources/:datasourceId/chunks",
    element: <DatasourceChunksPage />,
  },
  { path: "/data-registration", element: <DataRegistrationPage /> },
  { path: "/chat", element: <ChatPage /> },
  { path: "/chat/:sessionId", element: <ChatPage /> },
]);

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
);
