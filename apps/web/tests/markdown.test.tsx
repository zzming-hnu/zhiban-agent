import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Markdown } from "@/components/markdown";

describe("Markdown", () => {
  it("renders bold, lists, and headings", () => {
    render(<Markdown content={"**加粗**\n\n- 项目一\n- 项目二\n\n# 标题"} />);

    expect(screen.getByText("加粗")).toBeInTheDocument();
    expect(screen.getByText("项目一")).toBeInTheDocument();
    expect(screen.getByText("标题")).toBeInTheDocument();
  });

  it("strips raw HTML to prevent XSS", () => {
    render(
      <Markdown content={'你好 <script>alert("xss")</script> <img src=x onerror=alert(1)>'} />,
    );

    // The script tag must not be rendered as an element.
    expect(screen.queryByText("xss")).not.toBeInTheDocument();
    expect(document.querySelector("script")).toBeNull();
    expect(document.querySelector("img")).toBeNull();
  });

  it("renders external links safely", () => {
    render(<Markdown content="[示例](https://example.com)" />);

    const link = screen.getByText("示例");
    expect(link).toHaveAttribute("href", "https://example.com");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });
});
