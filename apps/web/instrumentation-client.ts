import posthog from "posthog-js";

if (
  process.env.NODE_ENV === "development" &&
  !process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN
) {
  console.error(
    "NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN variable required by PostHog is missing or un-configured, this causes events to be silently missed. This error stops appearing once NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN is configured",
  );
}

if (process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN) {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_PROJECT_TOKEN, {
    api_host: "/ingest",
    ui_host: "https://us.posthog.com",
    defaults: "2026-05-30",
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: true,
    capture_exceptions: true,
    disable_session_recording: true,
    opt_out_capturing_by_default: true,
    person_profiles: "never",
    persistence: "localStorage",
    respect_dnt: true,
    debug: process.env.NODE_ENV === "development",
  });
}
