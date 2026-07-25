"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import posthog from "posthog-js";
import { captureAnalytics } from "@/lib/analytics";

const preferenceKey = "imarsinyal-analytics-consent";
const openPreferenceEvent = "imarsinyal:open-analytics-preferences";

export function AnalyticsConsent({
  projectToken,
  apiHost,
}: {
  projectToken: string;
  apiHost: string;
}) {
  const pathname = usePathname();
  const enabled = projectToken.startsWith("phc_");
  const [prompt, setPrompt] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    if (!posthog.__loaded) {
      posthog.init(projectToken, {
        api_host: apiHost,
        defaults: "2026-05-30",
        autocapture: false,
        capture_pageview: false,
        capture_pageleave: true,
        disable_session_recording: true,
        opt_out_capturing_by_default: true,
        person_profiles: "never",
        persistence: "localStorage",
        respect_dnt: true,
      });
    }
    const preference = window.localStorage.getItem(preferenceKey);
    if (preference === "accepted") {
      posthog.opt_in_capturing();
    } else if (preference === "rejected") {
      posthog.opt_out_capturing();
    } else {
      setPrompt(true);
    }
  }, [apiHost, enabled, projectToken]);

  useEffect(() => {
    if (!enabled) return;
    function openPreferences() {
      setPrompt(true);
    }
    window.addEventListener(openPreferenceEvent, openPreferences);
    return () => window.removeEventListener(openPreferenceEvent, openPreferences);
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !posthog.__loaded || posthog.has_opted_out_capturing()) return;
    posthog.capture("$pageview", {
      $current_url: window.location.href,
      path: pathname,
    });
  }, [enabled, pathname]);

  if (!enabled || !prompt) return null;

  return (
    <aside className="analytics-consent" aria-label="Analitik tercihi">
      <div>
        <strong>Anonim kullanım ölçümüne izin verir misiniz?</strong>
        <p>
          Ürünü geliştirmek için sayfa ve özellik kullanımını ölçüyoruz. E-posta,
          form içeriği ve oturum kaydı toplamıyoruz.
        </p>
      </div>
      <div className="analytics-consent-actions">
        <button
          type="button"
          className="button button-ghost-dark"
          onClick={() => {
            window.localStorage.setItem(preferenceKey, "rejected");
            posthog.opt_out_capturing();
            setPrompt(false);
          }}
        >
          Reddet
        </button>
        <button
          type="button"
          className="button button-primary"
          onClick={() => {
            window.localStorage.setItem(preferenceKey, "accepted");
            posthog.opt_in_capturing();
            posthog.capture("$pageview", {
              $current_url: window.location.href,
              path: pathname,
            });
            setPrompt(false);
          }}
        >
          İzin ver
        </button>
      </div>
    </aside>
  );
}

export function AnalyticsPreferenceButton() {
  return (
    <button
      type="button"
      className="footer-preference"
      onClick={() => window.dispatchEvent(new Event(openPreferenceEvent))}
    >
      Analitik tercihleri
    </button>
  );
}

export function captureFilterUse(filter: string, value: string | boolean) {
  captureAnalytics("event_filter_used", {
    filter,
    value: typeof value === "string" ? value || "all" : value,
  });
}
