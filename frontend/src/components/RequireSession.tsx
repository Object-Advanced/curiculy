import { useEffect } from "react";
import { Outlet } from "react-router";

import { goToSignIn, readToken } from "../api/client";

/** Sign-in still lives in the legacy app; without a session, send people there. */
export function RequireSession() {
  const token = readToken();
  useEffect(() => {
    if (!token) goToSignIn();
  }, [token]);
  return token ? <Outlet /> : null;
}
