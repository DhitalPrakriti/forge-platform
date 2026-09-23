"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/forge";
import { rememberRun } from "@/lib/storage";
import { Button } from "../ui/button";
import { Card, ErrorNotice } from "../ui/shared";

export function FollowUp({
  org,
  runId,
  versionId,
}: {
  org: string;
  runId: string;
  versionId: string;
}) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState<{
    message: string;
    key: string;
  } | null>(null);
  const send = useMutation({
    mutationFn: (value: { message: string; key: string }) =>
      api.createRun(
        org,
        {
          agent_version_id: versionId,
          parent_run_id: runId,
          input: { message: value.message },
        },
        value.key,
      ),
    onSuccess: (run) => {
      rememberRun(org, run.id);
      router.push(`/runs/${run.id}`);
    },
  });
  return (
    <Card
      title="Continue the conversation"
      subtitle="Your earlier messages and replies are included. This version’s tools remain available."
    >
      <form
        className="form-stack"
        onSubmit={(event) => {
          event.preventDefault();
          if (send.isPending || send.isSuccess || !message.trim()) return;
          const next = attempt ?? {
            message: message.trim(),
            key: crypto.randomUUID(),
          };
          setAttempt(next);
          send.mutate(next);
        }}
      >
        <label htmlFor="follow-up">Follow-up message</label>
        <textarea
          id="follow-up"
          rows={4}
          maxLength={20000}
          required
          value={message}
          disabled={!!attempt}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Ask a follow-up or paste the next snippet…"
        />
        <ErrorNotice error={send.error} />
        <Button
          disabled={send.isPending || send.isSuccess || !message.trim()}
          type="submit"
        >
          {send.isPending
            ? "Sending…"
            : send.isError
              ? "Retry same message"
              : "Send follow-up"}
        </Button>
        <p className="muted">
          Each turn has its own run record. Earlier tool actions are not
          replayed. Context is limited to 10 prior turns and 60,000 characters;
          model calls may incur charges.
        </p>
      </form>
    </Card>
  );
}
