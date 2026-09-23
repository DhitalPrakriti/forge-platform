import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { expect, test, vi } from "vitest";
import { ModelHealthPanel } from "../components/models/model-health";
import { api } from "../lib/api/forge";
import { versionSchema } from "../lib/schemas";

function show() {
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <ModelHealthPanel org="org" />
    </QueryClientProvider>,
  );
}
test("does not label an unobserved provider healthy", async () => {
  vi.spyOn(api, "modelHealth").mockResolvedValue([]);
  show();
  expect(await screen.findByText(/Availability is unknown/)).toBeVisible();
  vi.restoreAllMocks();
});
test("explains open circuits and exposes last failure", async () => {
  vi.spyOn(api, "modelHealth").mockResolvedValue([
    {
      provider: "openai",
      model: "gpt-test",
      state: "OPEN",
      failures: 3,
      open_until: "2026-09-18T12:00:00Z",
      probe_until: null,
      last_observed_at: "2026-09-18T11:59:30Z",
      last_error: "MODEL_TIMEOUT",
    },
  ]);
  show();
  expect(await screen.findByText("OPEN")).toBeVisible();
  expect(screen.getByText(/Temporarily skipped/)).toBeVisible();
  expect(screen.getByText("Last error: MODEL_TIMEOUT")).toBeVisible();
  vi.restoreAllMocks();
});
test("validates ordered fallback identifiers and caps the list", () => {
  const field = versionSchema.shape.fallback_models_text;
  expect(field.safeParse("gpt-4.1-mini\ngemini-3.1-flash-lite").success).toBe(
    true,
  );
  expect(field.safeParse("gpt-4.1-mini,gpt-4.1-mini").success).toBe(false);
  expect(
    field.safeParse(Array.from({ length: 11 }, (_, i) => `gpt-${i}`).join("\n"))
      .success,
  ).toBe(false);
});
