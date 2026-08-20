import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApiStatus } from "@/components/api-status";

describe("ApiStatus", () => {
  it("shows an explicit offline state when the API cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    render(<ApiStatus />);

    expect(screen.getByText("正在检查 API")).toBeInTheDocument();
    expect(await screen.findByText("API 尚未启动")).toBeInTheDocument();
  });
});
