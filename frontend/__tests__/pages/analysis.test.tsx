import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AnalysisPage from "@/app/dashboard/analysis/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => "/dashboard/analysis",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ id: "test" }),
}));

const mockBriefing = {
  id: "r1",
  report_date: "2026-02-15",
  report_type: "morning",
  status: "completed",
  ai_summary: {
    headline: "NVIDIA surges on AI chip demand",
    market_sentiment: "탐욕",
    kospi_direction: "상승",
    key_issues: [
      "AI semiconductor demand surge",
      "Fed rate decision pending",
    ],
    watchlist: [
      { code: "005930", name: "삼성전자", reason: "Semiconductor leader" },
      { code: "000660", name: "SK하이닉스", reason: "HBM demand" },
    ],
    risks: ["US-China trade tensions", "Won weakness"],
    strategy: "Focus on semiconductor and AI themes",
  },
  themes: [
    { name: "AI/반도체", relevance_score: 85, signals: ["NVDA +5%"] },
  ],
  created_at: "2026-02-15T06:30:00Z",
};

describe("AnalysisPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders with stock analysis tab active by default", async () => {
    await act(async () => {
      render(<AnalysisPage />);
    });

    expect(screen.getByText("Stock AI Analysis")).toBeInTheDocument();
    expect(screen.getByText("Market Briefing")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/stock code/i)).toBeInTheDocument();
  });

  it("shows analyze button disabled when input is empty", async () => {
    await act(async () => {
      render(<AnalysisPage />);
    });

    const btn = screen.getByRole("button", { name: /Analyze/i });
    expect(btn).toBeDisabled();
  });

  it("renders AiAnalysisTab after entering stock code", async () => {
    // AiAnalysisTab will call /analysis/ai-reports on mount
    mockedApi.get.mockResolvedValue({ data: [] } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    const input = screen.getByPlaceholderText(/stock code/i);
    await user.type(input, "005930");

    const btn = screen.getByRole("button", { name: /Analyze/i });
    expect(btn).not.toBeDisabled();
    await user.click(btn);

    // AiAnalysisTab should be rendered (it shows a loading or initial state)
    await waitFor(() => {
      expect(mockedApi.get).toHaveBeenCalledWith(
        "/analysis/ai-reports",
        expect.objectContaining({
          params: expect.objectContaining({ stock_code: "005930" }),
        })
      );
    });
  });

  it("switches to market briefing tab and loads data", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockBriefing } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    const briefingTab = screen.getByRole("button", { name: /Market Briefing/i });
    await user.click(briefingTab);

    await waitFor(() => {
      expect(screen.getByText("NVIDIA surges on AI chip demand")).toBeInTheDocument();
    });

    expect(screen.getByText(/탐욕/)).toBeInTheDocument();
    expect(screen.getByText(/상승/)).toBeInTheDocument();
  });

  it("displays key issues in briefing", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockBriefing } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Market Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText("AI semiconductor demand surge")).toBeInTheDocument();
      expect(screen.getByText("Fed rate decision pending")).toBeInTheDocument();
    });
  });

  it("displays watchlist in briefing", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockBriefing } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Market Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText("삼성전자")).toBeInTheDocument();
      expect(screen.getByText("SK하이닉스")).toBeInTheDocument();
    });
  });

  it("displays risks and strategy in briefing", async () => {
    mockedApi.get.mockResolvedValueOnce({ data: mockBriefing } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Market Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText("US-China trade tensions")).toBeInTheDocument();
      expect(screen.getByText("Focus on semiconductor and AI themes")).toBeInTheDocument();
    });
  });

  it("toggles between morning and closing reports", async () => {
    mockedApi.get
      .mockResolvedValueOnce({ data: mockBriefing } as never)
      .mockResolvedValueOnce({
        data: { ...mockBriefing, report_type: "closing", ai_summary: { ...mockBriefing.ai_summary, headline: "KOSPI closes higher" } },
      } as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Market Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText("NVIDIA surges on AI chip demand")).toBeInTheDocument();
    });

    // Switch to closing
    await user.click(screen.getByRole("button", { name: /Market Close/i }));

    await waitFor(() => {
      expect(screen.getByText("KOSPI closes higher")).toBeInTheDocument();
    });
  });

  it("shows empty state when no briefing available", async () => {
    mockedApi.get.mockRejectedValueOnce(new Error("Not found") as never);

    await act(async () => {
      render(<AnalysisPage />);
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /Market Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/No briefing available/i)).toBeInTheDocument();
    });
  });
});
