import { afterEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { request } from "../src/lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("dashboard authentication errors", () => {
  it.each([400, 404, 429, 500])(
    "keeps the session on HTTP %i",
    async (status) => {
      const dispatchEvent = vi.fn(),
        removeItem = vi.fn();
      vi.stubGlobal("window", { dispatchEvent });
      vi.stubGlobal("sessionStorage", {
        getItem: () => "test-session",
        removeItem,
      });
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            new Response(
              JSON.stringify({ error: { code: "TEST", message: "failed" } }),
              { status },
            ),
          ),
      );
      await expect(request("/incidents", z.unknown())).rejects.toThrow(
        "failed",
      );
      expect(removeItem).not.toHaveBeenCalled();
      expect(dispatchEvent).not.toHaveBeenCalled();
    },
  );

  it("clears an expired session and notifies the shell", async () => {
    const dispatchEvent = vi.fn(),
      removeItem = vi.fn();
    vi.stubGlobal("window", { dispatchEvent });
    vi.stubGlobal("sessionStorage", { getItem: () => "expired", removeItem });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("{}", { status: 401 })),
    );
    await expect(request("/incidents", z.unknown())).rejects.toThrow();
    expect(removeItem).toHaveBeenCalledWith("tracelore.token");
    expect(dispatchEvent).toHaveBeenCalledOnce();
  });
});
