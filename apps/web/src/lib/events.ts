import { seedEvents } from "@/data/seed-events";
import { firestoreDb } from "./firestore";
import type { EventFilters, PlanningEvent } from "./types";

const cloneSeed = (): PlanningEvent[] =>
  seedEvents.map((event) => structuredClone(event));

function matches(event: PlanningEvent, filters: EventFilters): boolean {
  if (event.publication_status === "withheld") return false;
  if (filters.district && event.district !== filters.district) return false;
  if (filters.stage && event.stage !== filters.stage) return false;
  if (filters.category && !event.categories.includes(filters.category)) return false;
  if (filters.minImpact && event.impact_score < filters.minImpact) return false;
  if (filters.fromDate && event.event_date < filters.fromDate) return false;
  if (filters.toDate && event.event_date > filters.toDate) return false;
  if (filters.query) {
    const haystack = [
      event.title,
      event.summary,
      event.district,
      event.neighborhood,
      ...event.parcels,
    ]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase("tr-TR");
    if (!haystack.includes(filters.query.toLocaleLowerCase("tr-TR"))) return false;
  }
  return true;
}

export async function listEvents(
  filters: EventFilters = {},
  limit = 100,
): Promise<PlanningEvent[]> {
  const db = firestoreDb();
  let events: PlanningEvent[];

  if (!db) {
    events = cloneSeed();
  } else {
    const snapshot = await db
      .collection("planning_events")
      .where("publication_status", "in", ["source_only", "verified_ai"])
      .orderBy("event_date", "desc")
      .limit(Math.min(limit, 200))
      .get();
    events = snapshot.docs.map((doc) => doc.data() as PlanningEvent);
    if (!events.length && process.env.ALLOW_SEED_FALLBACK !== "false") {
      events = cloneSeed();
    }
  }

  return events
    .filter((event) => matches(event, filters))
    .sort(
      (a, b) =>
        b.event_date.localeCompare(a.event_date) ||
        b.impact_score - a.impact_score,
    )
    .slice(0, limit);
}

export async function getEventBySlug(
  slug: string,
): Promise<PlanningEvent | null> {
  const db = firestoreDb();
  if (db) {
    const snapshot = await db
      .collection("planning_events")
      .where("slug", "==", slug)
      .limit(1)
      .get();
    if (!snapshot.empty) return snapshot.docs[0].data() as PlanningEvent;
  }
  return cloneSeed().find((event) => event.slug === slug) ?? null;
}

export async function getEventsByIds(ids: string[]): Promise<PlanningEvent[]> {
  if (!ids.length) return [];
  const all = await listEvents({}, 200);
  return all.filter((event) => ids.includes(event.id));
}

export async function eventDistricts(): Promise<string[]> {
  const events = await listEvents({}, 200);
  return [...new Set(events.map((event) => event.district))].sort((a, b) =>
    a.localeCompare(b, "tr-TR"),
  );
}
