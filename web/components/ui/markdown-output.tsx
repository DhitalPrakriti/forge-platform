"use client";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownOutput({ text }: { text: string }) {
  return (
    <div className="markdown-output">
      <Markdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={["img"]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </Markdown>
    </div>
  );
}
