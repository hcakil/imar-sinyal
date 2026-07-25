"use client";

import posthog from "posthog-js";

type AnalyticsValue = string | number | boolean | null;

export function captureAnalytics(
  event: string,
  properties?: Record<string, AnalyticsValue>,
) {
  if (typeof window === "undefined" || !posthog.__loaded) return;
  if (posthog.has_opted_out_capturing()) return;
  posthog.capture(event, properties);
}
