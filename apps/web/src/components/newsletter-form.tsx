"use client";

import { FormEvent, useState } from "react";

const districts = [
  "Çankaya",
  "Mamak",
  "Yenimahalle",
  "Sincan",
  "Etimesgut",
  "Gölbaşı",
  "Keçiören",
  "Polatlı",
  "Beypazarı",
  "Haymana",
];

export function NewsletterForm({
  mode = "inline",
}: {
  mode?: "inline" | "full";
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [state, setState] = useState<
    "idle" | "sending" | "success" | "error"
  >("idle");
  const [message, setMessage] = useState("");

  function toggleDistrict(district: string) {
    setSelected((current) => {
      if (current.includes(district)) {
        return current.filter((item) => item !== district);
      }
      if (current.length >= 3) return current;
      return [...current, district];
    });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("sending");
    setMessage("");
    const form = new FormData(event.currentTarget);

    try {
      const response = await fetch("/api/subscribers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.get("email"),
          districts: selected,
          consent: form.get("consent") === "on",
          company: form.get("company"),
        }),
      });
      const payload = (await response.json()) as { message?: string };
      if (!response.ok) throw new Error(payload.message || "Kayıt tamamlanamadı.");
      setState("success");
      setMessage(
        payload.message ||
          "Kaydınız alındı. İlk bülten hazır olduğunda haber vereceğiz.",
      );
      event.currentTarget.reset();
      setSelected([]);
    } catch (error) {
      setState("error");
      setMessage(
        error instanceof Error ? error.message : "Beklenmeyen bir hata oluştu.",
      );
    }
  }

  if (state === "success") {
    return (
      <div className="form-success" role="status">
        <span aria-hidden="true">✓</span>
        <div>
          <strong>Listeye eklendiniz.</strong>
          <p>{message}</p>
        </div>
      </div>
    );
  }

  return (
    <form
      className={`newsletter-form newsletter-${mode}`}
      onSubmit={submit}
      noValidate
    >
      <div className="honeypot" aria-hidden="true">
        <label htmlFor={`company-${mode}`}>Şirket</label>
        <input
          id={`company-${mode}`}
          name="company"
          tabIndex={-1}
          autoComplete="off"
        />
      </div>
      <div className="email-row">
        <label className="sr-only" htmlFor={`email-${mode}`}>
          E-posta adresi
        </label>
        <input
          id={`email-${mode}`}
          name="email"
          type="email"
          placeholder="is@adresiniz.com"
          autoComplete="email"
          required
        />
        <button type="submit" disabled={state === "sending"}>
          {state === "sending" ? "Kaydediliyor…" : "Ücretsiz katıl"}
        </button>
      </div>
      {mode === "full" ? (
        <fieldset className="district-picker">
          <legend>
            Öncelikli ilçeler <span>İsteğe bağlı · En fazla 3</span>
          </legend>
          <div>
            {districts.map((district) => (
              <button
                key={district}
                type="button"
                aria-pressed={selected.includes(district)}
                onClick={() => toggleDistrict(district)}
              >
                {selected.includes(district) ? "✓ " : ""}
                {district}
              </button>
            ))}
          </div>
        </fieldset>
      ) : null}
      <label className="consent">
        <input name="consent" type="checkbox" required />
        <span>
          Haftalık bülteni almak ve{" "}
          <a href="/gizlilik" target="_blank">
            gizlilik metnini
          </a>{" "}
          kabul ediyorum.
        </span>
      </label>
      {message ? (
        <p className="form-error" role="alert">
          {message}
        </p>
      ) : null}
    </form>
  );
}
