import { describe, expect, it } from "vitest";

import { newIdempotencyKey } from "./client";

describe("idempotency keys", () => {
  it("uses randomUUID when the page is a secure context", () => {
    expect(newIdempotencyKey()).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("still makes a key over plain HTTP, where randomUUID is missing", () => {
    // Shadow the prototype method on this instance, as an insecure page would lack it.
    Object.defineProperty(crypto, "randomUUID", { value: undefined, configurable: true });
    try {
      const key = newIdempotencyKey();
      expect(key).toMatch(/^[0-9a-f]{32}$/);
      expect(newIdempotencyKey()).not.toBe(key);
    } finally {
      delete (crypto as { randomUUID?: unknown }).randomUUID;
    }
    expect(typeof crypto.randomUUID).toBe("function");
  });
});
