import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { listEvents } from "@/lib/events";

const querySchema = z.object({
  district: z.string().trim().max(80).optional(),
  stage: z
    .enum([
      "council_approved",
      "on_appeal",
      "appeal_ended",
      "expired",
      "withdrawn",
    ])
    .optional(),
  category: z
    .enum([
      "construction_conditions",
      "land_use",
      "plan_note",
      "public_infrastructure",
      "transportation",
      "procedural",
    ])
    .optional(),
  q: z.string().trim().max(120).optional(),
  minImpact: z.coerce.number().int().min(0).max(100).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(30),
});

export async function GET(request: NextRequest) {
  const parsed = querySchema.safeParse(
    Object.fromEntries(request.nextUrl.searchParams.entries()),
  );
  if (!parsed.success) {
    return NextResponse.json(
      { error: "invalid_query", details: parsed.error.flatten() },
      { status: 400 },
    );
  }
  const { limit, q, ...filters } = parsed.data;
  const events = await listEvents({ ...filters, query: q }, limit);
  return NextResponse.json(
    { count: events.length, events },
    {
      headers: {
        "Cache-Control": "public, max-age=60, s-maxage=900",
      },
    },
  );
}
