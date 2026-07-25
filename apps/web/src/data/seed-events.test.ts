import { describe, expect, it } from "vitest";
import { seedEvents } from "./seed-events";

describe("regression seed", () => {
  it("contains the eleven preserved extractions", () => {
    expect(seedEvents).toHaveLength(11);
  });

  it("keeps Yuva population density out of emsal", () => {
    const event = seedEvents.find((item) => item.neighborhood === "Yuva");
    expect(event?.changes.emsal.new_value).toBeNull();
    expect(event?.changes.density.new_value).toBe("121–250");
    expect(event?.changes.density.unit).toBe("kişi/ha");
  });

  it("keeps Korkutreis TAKS out of emsal", () => {
    const event = seedEvents.find((item) => item.neighborhood === "Korkutreis");
    expect(event?.changes.emsal.new_value).toBeNull();
    expect(event?.changes.taks.new_value).toBe("0.60");
  });

  it("keeps Beytepe UIP and NIP separate and linked", () => {
    const beytepe = seedEvents.filter((item) => item.neighborhood === "Beytepe");
    expect(beytepe).toHaveLength(2);
    expect(new Set(beytepe.flatMap((item) => item.plan_scales))).toEqual(
      new Set(["1/1000", "1/5000"]),
    );
    expect(beytepe.every((item) => item.linked_event_ids.length === 1)).toBe(true);
  });
});
