import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentsPage from "@/app/dashboard/agents/page";
import api from "@/lib/api";

jest.mock("@/lib/api");

const mockedApi = api as jest.Mocked<typeof api>;

const mockActiveStatus = {
  session_id: "s1",
  status: "active",
  session_type: "full_cycle",
  current_agent: "market_analyst",
  market_regime: "bullish",
  iteration_count: 5,
  started_at: new Date().toISOString(),
  recent_actions: [
    { agent: "analyst", action: "market_scan", timestamp: new Date().toISOString() },
    { agent: "executor", action: "order_placed", timestamp: new Date().toISOString() },
  ],
  pending_approvals: [
    {
      id: "a1",
      action_type: "trade",
      stock_code: "005930",
      side: "buy",
      quantity: 10,
      reason: "Strong bullish signal detected",
      created_at: new Date().toISOString(),
    },
  ],
};

describe("AgentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockResolvedValue({ data: null });
    mockedApi.post.mockResolvedValue({ data: {} });
  });

  it("renders page title", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("AI Trading Agents")).toBeInTheDocument();
    });
  });

  it("shows team description", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Team Leader coordinates 5 specialized agents for automated trading")).toBeInTheDocument();
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

  it("shows pending approvals section", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Pending Approvals")).toBeInTheDocument();
      expect(screen.getByText("No pending approvals")).toBeInTheDocument();
    });
  });

  it("renders 5 agent cards", async () => {
    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Market Analyst")).toBeInTheDocument();
      expect(screen.getByText("Strategy Search")).toBeInTheDocument();
      expect(screen.getByText("Risk Manager")).toBeInTheDocument();
      expect(screen.getByText("Execution")).toBeInTheDocument();
      expect(screen.getByText("Monitor")).toBeInTheDocument();
    });
  });

  it("shows active session status with details", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Session Active")).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(screen.getByText(/full_cycle/)).toBeInTheDocument();
    expect(screen.getAllByText(/bullish/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows stop button when active", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Stop Agent" })).toBeInTheDocument();
    });
  });

  it("shows recent activity when session active", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText(/analyst/)).toBeInTheDocument();
      expect(screen.getByText(/market_scan/)).toBeInTheDocument();
    });
  });

  it("renders pending approval with approve/reject buttons", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Approval Required")).toBeInTheDocument();
      expect(screen.getByText(/005930/)).toBeInTheDocument();
      expect(screen.getByText("Approve")).toBeInTheDocument();
      expect(screen.getByText("Reject")).toBeInTheDocument();
    });
  });

  it("calls approve API when approve clicked", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });
    const user = userEvent.setup();

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Approve")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/agents/approvals/a1", { approved: true });
    });
  });

  it("calls reject API when reject clicked", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });
    const user = userEvent.setup();

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Reject")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Reject"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/agents/approvals/a1", { approved: false });
    });
  });

  it("starts agent session on button click", async () => {
    mockedApi.post.mockResolvedValue({ data: { ...mockActiveStatus, pending_approvals: [] } });
    const user = userEvent.setup();

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Start Agent" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Start Agent" }));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/agents/start", { session_type: "full_cycle" });
    });
  });

  it("highlights current agent card", async () => {
    mockedApi.get.mockResolvedValue({ data: mockActiveStatus });

    render(<AgentsPage />);

    await waitFor(() => {
      expect(screen.getByText("Currently active...")).toBeInTheDocument();
    });
  });
});
