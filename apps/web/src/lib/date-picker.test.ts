import { describe, expect, it } from "vitest";
import {
  formatTurkishNumericDate,
  fromIsoDate,
  mondayFirstOffset,
  toIsoDate,
} from "./date-picker";

describe("Turkish date picker helpers", () => {
  it("round-trips ISO dates without timezone drift", () => {
    expect(toIsoDate(fromIsoDate("2026-07-25")!)).toBe("2026-07-25");
    expect(formatTurkishNumericDate("2026-07-25")).toBe("25.07.2026");
  });

  it("rejects invalid dates", () => {
    expect(fromIsoDate("2026-02-30")).toBeNull();
    expect(formatTurkishNumericDate("not-a-date")).toBe("gg.aa.yyyy");
  });

  it("starts calendar weeks on Monday", () => {
    expect(mondayFirstOffset(2026, 6)).toBe(2);
  });
});
