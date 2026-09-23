"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, Link2 } from "lucide-react";
import { api } from "@/lib/api/forge";
import {
  identitySchema,
  organizationIdSchema,
  type IdentityValues,
} from "@/lib/schemas";
import { useWorkspace } from "../layout/providers";
import { Button } from "../ui/button";
import { Card, ErrorNotice, Field, PageHeading } from "../ui/shared";
export function WorkspaceScreen() {
  const { workspace, connect } = useWorkspace();
  const router = useRouter();
  const createForm = useForm<IdentityValues>({
    resolver: zodResolver(identitySchema),
    defaultValues: { name: "", slug: "" },
  });
  const connectForm = useForm<{ id: string }>({
    resolver: zodResolver(organizationIdSchema),
    defaultValues: { id: "" },
  });
  const create = useMutation({
    mutationFn: api.createOrganization,
    onSuccess: (org) => {
      connect(org);
      router.push("/agents");
    },
  });
  const existing = useMutation({
    mutationFn: api.organization,
    onSuccess: (org) => {
      connect(org);
      router.push("/agents");
    },
  });
  return (
    <>
      <PageHeading
        eyebrow="YOUR WORKSPACE"
        title={workspace ? "Workspace settings" : "A home for your agents."}
        description="Choose an organization once. FORGE fills in the organization ID for every request after that."
      />
      {workspace && (
        <div className="notice">
          <Building2 size={18} />
          <div>
            <strong>Connected to {workspace.name}</strong>
            <p className="mono break-word">{workspace.id}</p>
          </div>
        </div>
      )}
      <div className="two-column">
        <Card
          title="Create a workspace"
          subtitle="Start fresh with an organization in your local database."
        >
          <form
            onSubmit={createForm.handleSubmit((values) =>
              create.mutate(values),
            )}
            className="form-stack"
            noValidate
          >
            <Field
              name="workspace-name"
              label="Workspace name"
              error={createForm.formState.errors.name?.message}
            >
              <input
                id="workspace-name"
                placeholder="My development workspace"
                {...createForm.register("name")}
                aria-invalid={!!createForm.formState.errors.name}
              />
            </Field>
            <Field
              name="workspace-slug"
              label="Workspace slug"
              hint="A unique name using lowercase letters, numbers, and hyphens."
              error={createForm.formState.errors.slug?.message}
            >
              <input
                id="workspace-slug"
                placeholder="my-workspace"
                {...createForm.register("slug")}
                aria-invalid={!!createForm.formState.errors.slug}
              />
            </Field>
            <ErrorNotice error={create.error} />
            <Button
              disabled={create.isPending || existing.isPending}
              type="submit"
            >
              {create.isPending ? "Creating…" : "Create workspace"}
              <ArrowRight size={16} />
            </Button>
          </form>
        </Card>
        <Card
          title="Connect an existing workspace"
          subtitle="Already created an organization in Swagger? Use its returned id."
        >
          <form
            onSubmit={connectForm.handleSubmit(({ id }) => existing.mutate(id))}
            className="form-stack"
            noValidate
          >
            <Field
              name="organization-id"
              label="Organization ID"
              hint="Paste the UUID value, not the words X-Organization-ID."
              error={connectForm.formState.errors.id?.message}
            >
              <input
                id="organization-id"
                className="mono"
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                {...connectForm.register("id")}
                aria-invalid={!!connectForm.formState.errors.id}
              />
            </Field>
            <ErrorNotice error={existing.error} />
            <Button
              variant="outline"
              disabled={existing.isPending || create.isPending}
              type="submit"
            >
              <Link2 size={16} />
              {existing.isPending ? "Checking workspace…" : "Connect workspace"}
            </Button>
          </form>
          <div className="inset-note">
            The API verifies this workspace exists before connecting. Recent
            workspaces are remembered in this browser.
          </div>
        </Card>
      </div>
      <p className="subtle-note">
        Local development only. Workspace selection provides organization
        context; it does not sign you in or verify membership.
      </p>
    </>
  );
}
