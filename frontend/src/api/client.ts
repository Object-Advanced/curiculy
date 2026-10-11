import createClient, { type Middleware } from "openapi-fetch";

import type { components, paths } from "./schema";

export type Lesson = components["schemas"]["AssignmentRead"];
export type LessonStatus = components["schemas"]["AssignmentStatus"];
export type Me = components["schemas"]["TokenUserRead"];
export type Student = components["schemas"]["StudentRead"];

// Until cookie sessions land (Phase 3), the React app shares the legacy app's
// sign-in: the same token under the same key, on the same origin.
export const AUTH_TOKEN_KEY = "auth_token";

export function readToken(): string | null {
  try {
    return window.localStorage.getItem(AUTH_TOKEN_KEY);
  } catch {
    return null;
  }
}

/** No usable sign-in: hand over to the legacy app, which shows sign-in. */
export function goToSignIn(): void {
  window.location.assign("/");
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailOf(error: unknown): string | null {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
  }
  return null;
}

export function toApiError(response: Response, error: unknown): ApiError {
  return new ApiError(response.status, detailOf(error) ?? `Request failed (${response.status})`);
}

/**
 * A random key for a write. `crypto.randomUUID` exists only on HTTPS and
 * localhost; a home server reached over plain HTTP still gets a key from
 * `getRandomValues`, like the legacy app's newIdempotencyKey.
 */
export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

const session: Middleware = {
  onRequest({ request }) {
    const token = readToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    // Writes carry a key so a retried request is applied once (app/core/idempotency.py).
    if (request.method !== "GET") request.headers.set("Idempotency-Key", newIdempotencyKey());
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401) goToSignIn();
    return response;
  },
};

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Resolve fetch per call, so test doubles (MSW) patched in later still apply.
  fetch: (request) => globalThis.fetch(request),
});
api.use(session);
