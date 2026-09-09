"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { Badge, Card, ErrorNotice, JsonDetails, Field } from "../ui/shared";
import { Button } from "../ui/button";
import { ConfirmDialog } from "../ui/confirm-dialog";

export function ApprovalPanel({
  org,
  runId,
  status,
  automatic = false,
}: {
  org: string;
  runId: string;
  status: string;
  automatic?: boolean;
}) {
  const client = useQueryClient();
  const [token, setToken] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState<{
    id: string;
    verdict: "approve" | "deny";
  } | null>(null);
  const approvals = useQuery({
    queryKey: [org, "approvals", runId],
    queryFn: () => api.approvals(org, runId),
    refetchInterval: status === "WAITING_FOR_APPROVAL" ? 2000 : false,
  });
  const action = useMutation({
    mutationFn: async ({
      id,
      verdict,
    }: {
      id: string;
      verdict: "approve" | "deny" | "resume";
    }) => {
      if (verdict === "resume") return api.resumeRun(org, runId, token);
      return api.decideApproval(org, id, verdict, reason.trim(), token);
    },
    onSuccess: () => {
      setConfirm(null);
      void client.invalidateQueries({ queryKey: [org] });
    },
  });
  if (!approvals.data?.length && !approvals.error) return null;
  return (
    <Card
      title="Refund approvals"
      subtitle={
        automatic
          ? "Review the exact request. Approval schedules the worker to continue automatically."
          : "Review the exact request. Approval is saved before you resume the run."
      }
    >
      <ErrorNotice
        error={approvals.error || action.error}
        retry={() => void approvals.refetch()}
      />
      {status === "WAITING_FOR_APPROVAL" && (
        <div className="form-stack">
          <p className="inset-note">
            Local reviewer credential only; this is not production login. The
            credential stays in this component’s memory and is sent only with
            approval actions. Waiting time counts toward the run deadline.
          </p>
          <Field name="reviewer-token" label="Local reviewer credential">
            <input
              id="reviewer-token"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </Field>
          <Field name="decision-reason" label="Decision reason">
            <textarea
              id="decision-reason"
              maxLength={2000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </Field>
        </div>
      )}
      {approvals.data?.map((a) => (
        <div className="model-call" key={a.id}>
          <h3>{a.summary}</h3>
          <Badge>{a.status}</Badge>
          <p>Expires: {new Date(a.expires_at).toLocaleString()}</p>
          <p className="mono break-word">Request hash: {a.request_hash}</p>
          <JsonDetails
            label="Exact refund request"
            value={a.requested_payload}
          />
          {a.reviewed_by && (
            <p>
              Reviewer: {a.reviewed_by} · {a.decision_reason}
            </p>
          )}
          {status === "WAITING_FOR_APPROVAL" && (
            <div className="actions">
              {a.status === "PENDING" && (
                <>
                  {(["approve", "deny"] as const).map((verdict) => (
                    <Button
                      key={verdict}
                      variant={verdict === "deny" ? "outline" : "default"}
                      disabled={!token || !reason.trim() || action.isPending}
                      onClick={() => setConfirm({ id: a.id, verdict })}
                    >
                      {verdict === "approve" ? "Approve refund" : "Deny refund"}
                    </Button>
                  ))}
                </>
              )}
              {a.status === "APPROVED" && (
                <Button
                  disabled={!token || action.isPending}
                  onClick={() => action.mutate({ id: a.id, verdict: "resume" })}
                >
                  {automatic ? "Wake worker again" : "Resume approved run"}
                </Button>
              )}
            </div>
          )}
        </div>
      ))}
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(open) => {
          if (!open) setConfirm(null);
        }}
        title={
          confirm?.verdict === "approve"
            ? "Approve this exact refund?"
            : "Deny this refund?"
        }
        description={
          automatic
            ? "Your decision and reason will be saved. Approval schedules execution of this exact request; denial cancels the run."
            : "Your decision and reason will be saved. Denial cancels the run. Approval allows you to resume while the request remains valid and unexpired."
        }
        confirmLabel="Save decision"
        pending={action.isPending}
        onConfirm={() => confirm && action.mutate(confirm)}
      />
    </Card>
  );
}
