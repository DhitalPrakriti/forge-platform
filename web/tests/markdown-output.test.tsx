import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { MarkdownOutput } from "../components/ui/markdown-output";

test("renders Markdown and preserves code indentation", () => {
  const { container } = render(
    <MarkdownOutput
      text={
        "### Review\n\n**Important**\n\n```python\ndef f():\n    return 1\n```"
      }
    />,
  );
  expect(screen.getByRole("heading", { name: "Review" })).toBeInTheDocument();
  expect(container.querySelector("strong")).toHaveTextContent("Important");
  expect(container.querySelector("pre code")?.textContent).toContain(
    "    return 1",
  );
});

test("does not render raw HTML, remote images, or executable links", () => {
  const { container } = render(
    <MarkdownOutput
      text={
        "<script>alert(1)</script>\n\n![tracker](https://example.com/pixel)\n\n[bad](javascript:alert%281%29)"
      }
    />,
  );
  expect(container.querySelector("script")).toBeNull();
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector('a[href^="javascript:"]')).toBeNull();
});
