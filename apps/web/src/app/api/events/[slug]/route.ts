import { NextResponse } from "next/server";
import { getEventBySlug } from "@/lib/events";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ slug: string }> },
) {
  const { slug } = await params;
  const event = await getEventBySlug(slug);
  if (!event || event.publication_status === "withheld") {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  return NextResponse.json(
    { event },
    {
      headers: {
        "Cache-Control": "public, max-age=60, s-maxage=900",
      },
    },
  );
}
