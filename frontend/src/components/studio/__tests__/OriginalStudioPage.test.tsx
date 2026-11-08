import { vi, describe, it, expect, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import OriginalStudioPage from "../OriginalStudioPage";
import { useStudioWorkspaceStore } from "@/stores/studio/workspaceStore";

const replace = vi.fn();
const router = { replace };
const setActiveTab = vi.fn();
let query = "";

vi.mock("next/navigation", () => ({
  usePathname: () => "/studio",
  useRouter: () => router,
  useSearchParams: () => new URLSearchParams(query),
}));
vi.mock("../StudioStore", () => ({
  StudioProvider: ({ children }: { children: React.ReactNode }) => children,
}));
vi.mock("../StudioLayout", () => ({
  __esModule: true,
  default: () => <main data-testid="original-studio-layout">Develop workspace</main>,
}));

describe("OriginalStudioPage", () => {
  beforeEach(() => {
    query = "";
    replace.mockReset();
    setActiveTab.mockReset();
    useStudioWorkspaceStore.setState({ activeTab: "develop", setActiveTab });
  });

  it("mounts the original workspace with Develop as the default", () => {
    render(<OriginalStudioPage />);

    expect(screen.getByTestId("original-studio-layout")).toBeVisible();
    expect(setActiveTab).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });

  it("maps a canonical Results deep link to the current results workspace", async () => {
    query = "mode=results";
    render(<OriginalStudioPage />);

    await waitFor(() => expect(setActiveTab).toHaveBeenCalledWith("tearsheet"));
    expect(replace).not.toHaveBeenCalled();
  });

  it("migrates a legacy Stress deep link into Validate", async () => {
    query = "mode=stress";
    render(<OriginalStudioPage />);

    await waitFor(() => expect(setActiveTab).toHaveBeenCalledWith("validate"));
  });

  it("writes supported internal navigation back to the canonical query", async () => {
    render(<OriginalStudioPage />);
    act(() => useStudioWorkspaceStore.setState({ activeTab: "validate" }));

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/studio?mode=validate", { scroll: false });
    });
  });

  it("opens the integrated Portfolio mode from a canonical deep link", async () => {
    useStudioWorkspaceStore.setState({ activeTab: "validate" });
    query = "mode=portfolio&run=run-123";
    render(<OriginalStudioPage />);

    await waitFor(() => {
      expect(setActiveTab).toHaveBeenCalledWith("portfolio");
    });
  });

  it("normalizes invalid modes to Develop", async () => {
    query = "mode=unknown";
    render(<OriginalStudioPage />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/studio?mode=develop", { scroll: false }));
  });
});
