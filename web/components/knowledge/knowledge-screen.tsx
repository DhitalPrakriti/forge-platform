"use client";
import { useState, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { useWorkspace } from "../layout/providers";
import { WorkspaceScreen } from "../workspace/workspace-screen";
import { Button } from "../ui/button";
import { Card, ErrorNotice, PageHeading, Field } from "../ui/shared";
import { DocumentPicker } from "./document-picker";

export function KnowledgeScreen() {
  const { workspace } = useWorkspace();
  return workspace ? (
    <WorkspaceKnowledge key={workspace.id} org={workspace.id} />
  ) : (
    <WorkspaceScreen />
  );
}
function WorkspaceKnowledge({ org }: { org: string }) {
  const client = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const upload = useMutation({
    mutationFn: async () => {
      const file = fileInput.current?.files?.[0];
      if (!file || !title.trim())
        throw new Error("Enter a title and choose a document.");
      if (!file.size || file.size > 3_000_000)
        throw new Error("Choose a nonempty file up to 3 MB.");
      const content_base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1]);
        reader.onerror = () => reject(new Error("Could not read this file."));
        reader.readAsDataURL(file);
      });
      return api.uploadDocument(org, {
        title: title.trim(),
        filename: file.name,
        content_base64,
      });
    },
    onSuccess: () => {
      setTitle("");
      if (fileInput.current) fileInput.current.value = "";
      void client.invalidateQueries({ queryKey: [org, "documents"] });
    },
  });
  const search = useMutation({
    mutationFn: () => api.searchDocuments(org, selected, query),
  });
  return (
    <>
      <PageHeading
        eyebrow="WORKSPACE / KNOWLEDGE"
        title="Knowledge"
        description="Optional reference documents for your agents. Business actions still use separate tools and connections."
      />
      <Card
        title="Upload a document"
        subtitle="PDF, text or Markdown · up to 3 MB and 200,000 extracted characters"
      >
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            upload.mutate();
          }}
        >
          <Field name="document-title" label="Document title">
            <input
              id="document-title"
              value={title}
              maxLength={200}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
          </Field>
          <Field name="document-file" label="Document file">
            <input
              id="document-file"
              ref={fileInput}
              type="file"
              accept=".pdf,.txt,.md"
              required
            />
          </Field>
          <p className="muted">
            PDFs: selectable text, no password, at most 50 pages. No OCR or
            image extraction. Text and Markdown must be UTF-8. Original files
            are not retained; extracted passages are stored in PostgreSQL.
          </p>
          <Button type="submit" disabled={upload.isPending}>
            {upload.isPending ? "Extracting and saving…" : "Upload document"}
          </Button>
          <ErrorNotice error={upload.error} />
          {upload.isSuccess && (
            <p role="status">
              Saved “{upload.data.title}”. Select this document in a new agent
              version and enable Search documents.
            </p>
          )}
        </form>
      </Card>
      <Card
        title="Documents & search preview"
        subtitle="Preview keyword matches before giving an agent access. This selection only affects the preview."
      >
        <DocumentPicker
          org={org}
          selected={selected}
          onChange={(ids) => {
            setSelected(ids);
            search.reset();
          }}
        />
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            search.mutate();
          }}
        >
          <Field name="knowledge-query" label="Search keywords">
            <input
              id="knowledge-query"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                search.reset();
              }}
              maxLength={500}
              required
              placeholder="opening hours"
            />
          </Field>
          <Button
            type="submit"
            disabled={search.isPending || !selected.length || !query.trim()}
          >
            {search.isPending ? "Searching…" : "Preview search"}
          </Button>
        </form>
        <ErrorNotice error={search.error} />
        {search.data && (
          <div aria-live="polite">
            <p>{search.data.matches.length} matching passages</p>
            {search.data.matches.map((m) => (
              <blockquote key={`${m.document_id}-${m.chunk}`}>
                <strong>
                  {m.title} · {m.page ? `page ${m.page}, ` : ""}passage{" "}
                  {m.chunk}
                </strong>
                <p style={{ whiteSpace: "pre-wrap" }}>{m.excerpt}</p>
              </blockquote>
            ))}
            <p className="muted">
              English keyword search, not semantic search. Try different
              keywords when there are no matches.
            </p>
          </div>
        )}
      </Card>
    </>
  );
}
