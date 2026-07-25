"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  formatTurkishNumericDate,
  fromIsoDate,
  mondayFirstOffset,
  toIsoDate,
  turkishMonths,
  turkishWeekdays,
} from "@/lib/date-picker";

export function TurkishDatePicker({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: string;
  min?: string;
  max?: string;
  onChange: (value: string) => void;
}) {
  const initial = fromIsoDate(value) || new Date();
  const [open, setOpen] = useState(false);
  const [viewYear, setViewYear] = useState(initial.getFullYear());
  const [viewMonth, setViewMonth] = useState(initial.getMonth());
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function closeOnOutside(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [open]);

  const days = useMemo(() => {
    const offset = mondayFirstOffset(viewYear, viewMonth);
    const count = new Date(viewYear, viewMonth + 1, 0, 12).getDate();
    return [
      ...Array.from({ length: offset }, () => null),
      ...Array.from({ length: count }, (_, index) => index + 1),
    ];
  }, [viewMonth, viewYear]);

  function moveMonth(amount: number) {
    const next = new Date(viewYear, viewMonth + amount, 1, 12);
    setViewYear(next.getFullYear());
    setViewMonth(next.getMonth());
  }

  function selectDay(day: number) {
    onChange(toIsoDate(new Date(viewYear, viewMonth, day, 12)));
    setOpen(false);
  }

  const today = toIsoDate(new Date());

  return (
    <div className="date-field" ref={rootRef}>
      <span className="date-label">{label}</span>
      <button
        type="button"
        className="date-input"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((current) => !current)}
      >
        <span className={value ? "" : "date-placeholder"}>
          {formatTurkishNumericDate(value)}
        </span>
        <span className="calendar-symbol" aria-hidden="true">
          ▦
        </span>
      </button>
      {open ? (
        <div
          className="date-popover"
          role="dialog"
          aria-label={`${label} tarihi seçin`}
        >
          <div className="date-popover-header">
            <button
              type="button"
              aria-label="Önceki ay"
              onClick={() => moveMonth(-1)}
            >
              ←
            </button>
            <strong>
              {turkishMonths[viewMonth]} {viewYear}
            </strong>
            <button
              type="button"
              aria-label="Sonraki ay"
              onClick={() => moveMonth(1)}
            >
              →
            </button>
          </div>
          <div className="date-weekdays" aria-hidden="true">
            {turkishWeekdays.map((day) => (
              <span key={day}>{day}</span>
            ))}
          </div>
          <div className="date-days">
            {days.map((day, index) => {
              if (day === null) {
                return <span key={`empty-${index}`} />;
              }
              const date = new Date(viewYear, viewMonth, day, 12);
              const iso = toIsoDate(date);
              const disabled = Boolean((min && iso < min) || (max && iso > max));
              return (
                <button
                  type="button"
                  key={iso}
                  disabled={disabled}
                  aria-label={new Intl.DateTimeFormat("tr-TR", {
                    day: "numeric",
                    month: "long",
                    year: "numeric",
                  }).format(date)}
                  aria-pressed={iso === value}
                  className={iso === today ? "date-today" : ""}
                  onClick={() => selectDay(day)}
                >
                  {day}
                </button>
              );
            })}
          </div>
          <div className="date-popover-footer">
            <button
              type="button"
              onClick={() => {
                onChange("");
                setOpen(false);
              }}
            >
              Temizle
            </button>
            <button
              type="button"
              disabled={Boolean((min && today < min) || (max && today > max))}
              onClick={() => {
                onChange(today);
                setOpen(false);
              }}
            >
              Bugün
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
