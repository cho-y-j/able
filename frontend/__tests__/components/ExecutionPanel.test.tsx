import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ExecutionPanel from "@/app/dashboard/recipes/[id]/_components/ExecutionPanel";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockOrders = [
  {
    id: "o1",
    stock_code: "005930",
    side: "buy",
    order_type: "market",
    quantity: 20,
    avg_fill_price: 72000,
    kis_order_id: "KIS001",
    status: "filled",
    execution_strategy: "direct",
    slippage_bps: 2.1,
    error_message: null,
    created_at: "2026-02-10T09:30:00Z",
  },
  {
    id: "o2",
    stock_code: "000660",
    side: "sell",
    order_type: "limit",
    quantity: 10,
    avg_fill_price: null,
    kis_order_id: null,
    status: "failed",
    execution_strategy: "twap",
    slippage_bps: null,
    error_message: "API timeout",
    created_at: "2026-02-10T10:00:00Z",
  },
];

describe("ExecutionPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedApi.get.mockResolvedValue({ data: [] });
  });

  it("renders empty state when no orders", async () => {
    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={false} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("아직 실행 내역이 없습니다")).toBeInTheDocument();
    });
  });

  it("renders orders table when orders exist", async () => {
    mockedApi.get.mockResolvedValue({ data: mockOrders });

    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={true} stockCodes={["005930", "000660"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("005930")).toBeInTheDocument();
      expect(screen.getByText("000660")).toBeInTheDocument();
    });

    // Check buy/sell labels
    expect(screen.getByText("매수")).toBeInTheDocument();
    expect(screen.getByText("매도")).toBeInTheDocument();

    // Check status labels — "실패" appears in both stats card and order row
    expect(screen.getByText("체결")).toBeInTheDocument();
    expect(screen.getAllByText("실패").length).toBeGreaterThanOrEqual(1);
  });

  it("shows active status badge when isActive", async () => {
    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={true} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("자동매매 활성")).toBeInTheDocument();
    });
  });

  it("shows inactive status badge when not active", async () => {
    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={false} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("비활성")).toBeInTheDocument();
    });
  });

  it("calls execute API when button is clicked", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({
      data: { total_submitted: 1, total_failed: 0 },
    });

    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={true} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("지금 실행")).toBeInTheDocument();
    });

    await user.click(screen.getByText("지금 실행"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/recipes/r1/execute", {});
    });
  });

  it("shows execution result after successful execution", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({
      data: { total_submitted: 2, total_failed: 1 },
    });

    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={true} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("지금 실행")).toBeInTheDocument();
    });

    await user.click(screen.getByText("지금 실행"));

    await waitFor(() => {
      expect(screen.getByText(/2건 제출/)).toBeInTheDocument();
      expect(screen.getByText(/1건 실패/)).toBeInTheDocument();
    });
  });

  it("shows stats cards when orders exist", async () => {
    mockedApi.get.mockResolvedValue({ data: mockOrders });

    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={false} stockCodes={["005930"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText("총 주문")).toBeInTheDocument();
    });

    // 2 total orders, 1 success (filled), 1 fail
    expect(screen.getByText("총 주문")).toBeInTheDocument();
    expect(screen.getByText("성공")).toBeInTheDocument();
    // "실패" appears in both stats card label and order status — use getAllByText
    const failTexts = screen.getAllByText("실패");
    expect(failTexts.length).toBeGreaterThanOrEqual(1);
  });

  it("disables execute button when no recipeId", async () => {
    await act(async () => {
      render(
        <ExecutionPanel recipeId={null} isActive={false} stockCodes={[]} />
      );
    });

    await waitFor(() => {
      const btn = screen.getByText("지금 실행");
      expect(btn).toBeDisabled();
    });
  });

  it("shows stock count", async () => {
    await act(async () => {
      render(
        <ExecutionPanel recipeId="r1" isActive={false} stockCodes={["005930", "000660", "035720"]} />
      );
    });

    await waitFor(() => {
      expect(screen.getByText(/3개/)).toBeInTheDocument();
    });
  });
});
