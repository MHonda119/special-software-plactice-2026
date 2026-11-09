import { useSyncExternalStore } from "react";
import { authSession } from "./authSession.js";

export function useAuth() {
  return useSyncExternalStore(authSession.subscribe, authSession.getSnapshot);
}
