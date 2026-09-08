"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div role="alert" className="empty">
      <h1>This page could not load.</h1>
      <p className="muted">
        Try loading the page again. Your saved backend records are preserved.
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
