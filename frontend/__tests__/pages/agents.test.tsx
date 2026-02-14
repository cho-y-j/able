import { render, screen, waitFor } from "@testing-library/react";
import AgentsPage from "@/app/dashboard/agents/page";
import api from "@/lib/api";

jest.mock("@/lib/api");

const mockedApi = api as jest.Mocked<typeof api>;

describe("AgentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default: no active session
    mockedApi.get.mockResolvedValue({ data: null });
  });

  it("renders page title", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("AI Trading Agents")).toBeInTheDocument();
    });
  });

  it("shows start button when idle", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Start Agent" }),
      ).toBeInTheDocument();
    });
  });

  it("fetches agent status on mount", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(mockedApi.get).toHaveBeenCalledWith("/agents/status");
    });
  });

  it("shows activity log section", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Activity Log")).toBeInTheDocument();
    });
  });

  it("shows no activity message", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("No activity yet.")).toBeInTheDocument();
    });
  });
});
