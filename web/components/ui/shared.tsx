"use client";
import { cloneElement, type ReactElement, type ReactNode } from "react";
import { AlertCircle, ArrowLeft, ArrowRight, LoaderCircle } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { Button } from "./button";
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span
      className={`badge badge-${String(children).toLowerCase().replaceAll("_", "-")}`}
    >
      {children}
    </span>
  );
}
export function PageHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      {action}
    </header>
  );
}
export function Card({
  title,
  subtitle,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-header">
          <h2>{title}</h2>
          {subtitle && <p className="muted">{subtitle}</p>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </section>
  );
}
export function ErrorNotice({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div role="alert" className="error-notice">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <strong>
          {error instanceof Error ? error.message : "Something went wrong."}
        </strong>
        {error instanceof ApiError && (
          <p className="mono">
            {error.code}
            {error.traceId && <> · Trace: {error.traceId}</>}
          </p>
        )}
        {retry && (
          <Button variant="outline" size="sm" onClick={retry}>
            Try again
          </Button>
        )}
      </div>
    </div>
  );
}
export function Loading({ label = "Loading from FORGE…" }: { label?: string }) {
  return (
    <div role="status" className="loading">
      <LoaderCircle className="spin" size={20} />
      {label}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-mark">F</div>
      <h2>{title}</h2>
      <div className="muted">{children}</div>
    </div>
  );
}
export function Field({
  label,
  name,
  error,
  hint,
  children,
}: {
  label: string;
  name: string;
  error?: string;
  hint?: string;
  children: ReactElement<{
    "aria-describedby"?: string;
    "aria-invalid"?: boolean;
  }>;
}) {
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      {cloneElement(children, {
        "aria-describedby":
          [hint && `${name}-hint`, error && `${name}-error`]
            .filter(Boolean)
            .join(" ") || undefined,
        "aria-invalid": !!error,
      })}
      {hint && (
        <p id={`${name}-hint`} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${name}-error`} className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
export function JsonDetails({
  value,
  label = "View API data",
}: {
  value: unknown;
  label?: string;
}) {
  return (
    <details className="json-details">
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export function Pagination({
  offset,
  count,
  onChange,
}: {
  offset: number;
  count: number;
  onChange: (offset: number) => void;
}) {
  return (
    <div className="pagination">
      <span className="muted">
        {count
          ? `${offset + 1}–${offset + count} loaded`
          : "No entries on this page"}
      </span>
      <div className="actions">
        <Button
          variant="outline"
          size="sm"
          disabled={!offset}
          onClick={() => onChange(Math.max(0, offset - 20))}
        >
          <ArrowLeft size={14} />
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={count < 20}
          onClick={() => onChange(offset + 20)}
        >
          Next
          <ArrowRight size={14} />
        </Button>
      </div>
    </div>
  );
}
