"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/forge";
import { Button } from "../ui/button";
import { ErrorNotice, Loading, JsonDetails } from "../ui/shared";

export function DocumentPicker({
  org,
  selected,
  onChange,
}: {
  org: string;
  selected: string[];
  onChange: (ids: string[]) => void;
}) {
  const [offset, setOffset] = useState(0);
  const documents = useQuery({
    queryKey: [org, "documents", offset],
    queryFn: () => api.documents(org, offset),
    refetchOnWindowFocus: "always",
  });
  return (
    <div className="form-stack">
      <p>
        {selected.length} of 20 documents selected. Each upload is an immutable
        snapshot.
      </p>
      <ErrorNotice
        error={documents.error}
        retry={() => void documents.refetch()}
      />
      {documents.isPending && <Loading />}
      {documents.data?.length === 0 && (
        <p>No documents on this page. Upload documents in Knowledge.</p>
      )}
      {documents.data?.map((doc) => (
        <div key={doc.id}>
          <label className="tool-choice">
            <input
              type="checkbox"
              checked={selected.includes(doc.id)}
              disabled={!selected.includes(doc.id) && selected.length >= 20}
              onChange={(e) =>
                onChange(
                  e.target.checked
                    ? [...selected, doc.id]
                    : selected.filter((id) => id !== doc.id),
                )
              }
            />
            <span>
              <strong>{doc.title}</strong>
              <br />
              <span className="muted">
                {doc.filename} · {doc.character_count.toLocaleString()}{" "}
                characters · {doc.chunk_count} passages
              </span>
            </span>
          </label>
          <JsonDetails label={`Technical details: ${doc.title}`} value={doc} />
        </div>
      ))}
      <div className="actions">
        <Button
          type="button"
          variant="outline"
          disabled={offset === 0}
          onClick={() => setOffset(offset - 100)}
        >
          Previous documents
        </Button>
        <Button
          type="button"
          variant="outline"
          disabled={documents.data?.length !== 100}
          onClick={() => setOffset(offset + 100)}
        >
          More documents
        </Button>
        <Button
          type="button"
          variant="ghost"
          onClick={() => void documents.refetch()}
        >
          Refresh documents
        </Button>
        {selected.length > 0 && (
          <Button type="button" variant="ghost" onClick={() => onChange([])}>
            Clear document selection
          </Button>
        )}
      </div>
    </div>
  );
}
