"use client";

import type { ReactNode } from "react";
import { captureAnalytics } from "@/lib/analytics";

export function TrackedSourceLink({
  href,
  eventId,
  sourceArea,
  className,
  children,
}: {
  href: string;
  eventId: string;
  sourceArea: "primary" | "evidence";
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      className={className}
      href={href}
      target="_blank"
      rel="noreferrer"
      onClick={() =>
        captureAnalytics("official_source_opened", {
          event_id: eventId,
          source_area: sourceArea,
        })
      }
    >
      {children}
    </a>
  );
}
