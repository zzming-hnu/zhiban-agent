import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import Home from "@/app/page";

describe("Home", () => {
  it("renders the visible project foundation state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
      }),
    );

    render(<Home />);

    expect(
      screen.getByRole("heading", { name: /把每次对话.*变成可以延续的理解/ }),
    ).toBeInTheDocument();
    expect(screen.getByText("工程基础阶段")).toBeInTheDocument();
    expect(await screen.findByText("API 已连接")).toBeInTheDocument();
  });
});
