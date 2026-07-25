import { describe, expect, it } from "vitest";
import { seedEvents } from "@/data/seed-events";
import { listEvents } from "./events";

describe("event date filters", () => {
  it("applies inclusive from/to bounds", async () => {
    const dates = seedEvents.map((event) => event.event_date).sort();
    const fromDate = dates[Math.floor(dates.length / 3)];
    const toDate = dates[Math.floor((dates.length * 2) / 3)];

    const events = await listEvents({ fromDate, toDate }, 100);

    expect(events.length).toBeGreaterThan(0);
    expect(
      events.every(
        (event) =>
          event.event_date >= fromDate && event.event_date <= toDate,
      ),
    ).toBe(true);
  });
});
