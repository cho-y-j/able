import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ParamAdjustTab from "@/app/dashboard/strategies/[id]/_components/ParamAdjustTab";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

jest.mock("lucide-react", () => ({
  Loader2: (props: any) => <svg data-testid="icon-loader" {...props} />,
}));

const defaultProps = {
  strategyId: "strat-1",
  parameters: { fast_period: 12, slow_period: 26 },
  riskParams: { stop_loss: 3 },
  paramRanges: {
    fast_period: { type: "int", current: 12, min: 5, max: 50, choices: null },
    slow_period: { type: "int", current: 26, min: 10, max: 100, choices: null },
  },
  onRebacktestComplete: jest.fn(),
};

describe("ParamAdjustTab", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders preset buttons", () => {
    render(<ParamAdjustTab {...defaultProps} />);
    expect(screen.getByText("보수적")).toBeInTheDocument();
    expect(screen.getByText("공격적")).toBeInTheDocument();
    expect(screen.getByText("원래값")).toBeInTheDocument();
  });

  it("renders parameter labels", () => {
    render(<ParamAdjustTab {...defaultProps} />);
    expect(screen.getByText("fast_period")).toBeInTheDocument();
    expect(screen.getByText("slow_period")).toBeInTheDocument();
  });

  it("renders rebacktest button", () => {
    render(<ParamAdjustTab {...defaultProps} />);
    expect(screen.getByText("재백테스트 실행")).toBeInTheDocument();
  });

  it("shows min/max range info", () => {
    render(<ParamAdjustTab {...defaultProps} />);
    expect(screen.getByText("최소: 5")).toBeInTheDocument();
    expect(screen.getByText("최대: 50")).toBeInTheDocument();
    expect(screen.getByText("최소: 10")).toBeInTheDocument();
    expect(screen.getByText("최대: 100")).toBeInTheDocument();
  });

  it("applies conservative preset (25% toward min)", async () => {
    const user = userEvent.setup();
    render(<ParamAdjustTab {...defaultProps} />);

    await user.click(screen.getByText("보수적"));

    // fast_period: 12 + (5 - 12) * 0.25 = 12 - 1.75 = 10.25, rounded = 10
    const inputs = screen.getAllByRole("spinbutton");
    expect((inputs[0] as HTMLInputElement).value).toBe("10");
    // slow_period: 26 + (10 - 26) * 0.25 = 26 - 4 = 22
    expect((inputs[1] as HTMLInputElement).value).toBe("22");
  });

  it("applies aggressive preset (25% toward max)", async () => {
    const user = userEvent.setup();
    render(<ParamAdjustTab {...defaultProps} />);

    await user.click(screen.getByText("공격적"));

    // fast_period: 12 + (50 - 12) * 0.25 = 12 + 9.5 = 21.5, rounded = 22
    const inputs = screen.getAllByRole("spinbutton");
    expect((inputs[0] as HTMLInputElement).value).toBe("22");
    // slow_period: 26 + (100 - 26) * 0.25 = 26 + 18.5 = 44.5, rounded = 45
    expect((inputs[1] as HTMLInputElement).value).toBe("45");
  });

  it("resets to original values", async () => {
    const user = userEvent.setup();
    render(<ParamAdjustTab {...defaultProps} />);

    // First apply a preset
    await user.click(screen.getByText("공격적"));
    // Then reset
    await user.click(screen.getByText("원래값"));

    const inputs = screen.getAllByRole("spinbutton");
    expect((inputs[0] as HTMLInputElement).value).toBe("12");
    expect((inputs[1] as HTMLInputElement).value).toBe("26");
  });

  it("shows change count badge after modification", async () => {
    const user = userEvent.setup();
    render(<ParamAdjustTab {...defaultProps} />);

    await user.click(screen.getByText("보수적"));

    expect(screen.getByText(/2개 파라미터 변경됨/)).toBeInTheDocument();
    // "변경됨" badges on each changed param
    const changedBadges = screen.getAllByText("변경됨");
    expect(changedBadges.length).toBe(2);
  });

  it("calls API on rebacktest and shows comparison result", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({
      data: {
        composite_score: 78.5,
        grade: "B+",
        metrics: { total_return: 22.3, sharpe_ratio: 1.42, max_drawdown: -10.5 },
      },
    });

    render(<ParamAdjustTab {...defaultProps} />);

    await user.click(screen.getByText("재백테스트 실행"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith(
        "/analysis/strategies/strat-1/rebacktest",
        {
          parameters: { fast_period: 12, slow_period: 26 },
          risk_params: { stop_loss: 3 },
        }
      );
    });

    await waitFor(() => {
      // Comparison panel should appear
      expect(screen.getByText("변경 전후 비교")).toBeInTheDocument();
      // B+ appears in both comparison panel and history table
      const bPlusTexts = screen.getAllByText(/B\+/);
      expect(bPlusTexts.length).toBeGreaterThanOrEqual(1);
      // History entry
      expect(screen.getByText("최근 재백테스트 기록")).toBeInTheDocument();
    });

    expect(defaultProps.onRebacktestComplete).toHaveBeenCalled();
  });

  it("shows error message on rebacktest failure", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockRejectedValue({
      response: { data: { detail: "데이터 부족" } },
    });

    render(<ParamAdjustTab {...defaultProps} />);

    await user.click(screen.getByText("재백테스트 실행"));

    await waitFor(() => {
      expect(screen.getByText("재백테스트 실패")).toBeInTheDocument();
      expect(screen.getByText("데이터 부족")).toBeInTheDocument();
    });
  });

  it("renders select dropdown for categorical parameters", () => {
    const propsWithChoices = {
      ...defaultProps,
      parameters: { signal_type: "ema" },
      paramRanges: {
        signal_type: { type: "categorical", current: "ema", min: null, max: null, choices: ["ema", "sma", "wma"] },
      },
    };

    render(<ParamAdjustTab {...propsWithChoices} />);

    expect(screen.getByText("signal_type")).toBeInTheDocument();
    expect(screen.getByDisplayValue("ema")).toBeInTheDocument();
  });
});
