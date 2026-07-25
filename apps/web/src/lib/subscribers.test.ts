import { describe, expect, it } from "vitest";
import {
  normalizeEmail,
  readUnsubscribeToken,
  unsubscribeToken,
} from "./subscribers";

describe("subscriber tokens", () => {
  it("normalizes and round-trips a signed unsubscribe token", () => {
    process.env.UNSUBSCRIBE_SECRET = "test-secret-with-enough-entropy";
    const email = normalizeEmail("  TEST@Example.COM ");
    const token = unsubscribeToken(email);
    expect(readUnsubscribeToken(token)).toBe("test@example.com");
    expect(readUnsubscribeToken(`${token}broken`)).toBeNull();
  });
});
