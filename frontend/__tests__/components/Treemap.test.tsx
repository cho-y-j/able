import { render, screen } from "@testing-library/react";
import Treemap from "@/app/dashboard/portfolio/_components/Treemap";
import type { TreemapItem } from "@/app/dashboard/portfolio/_components/Treemap";

jest.mock("@/lib/charts", () => ({
  formatPct: (v: number) => `${v >= 0 ? "+" : ""}${v.toFixed(1)}%`,
}));

const items: TreemapItem[] = [
  { code: "005930", name: "삼성전자", value: 5000000, weight: 50, pnl_pct: 3.2 },
  { code: "035420", name: "NAVER", value: 3000000, weight: 30, pnl_pct: -1.5 },
  { code: "000660", name: "SK하이닉스", value: 2000000, weight: 20, pnl_pct: 0 },
];

describe("Treemap", () => {
  it("renders stock code cells", () => {
    render(<Treemap items={items} />);

    expect(screen.getByText("005930")).toBeInTheDocument();
    expect(screen.getByText("035420")).toBeInTheDocument();
    expect(screen.getByText("000660")).toBeInTheDocument();
  });

  it("renders pnl percentages", () => {
    render(<Treemap items={items} />);

    expect(screen.getByText("+3.2%")).toBeInTheDocument();
    expect(screen.getByText("-1.5%")).toBeInTheDocument();
    expect(screen.getByText("+0.0%")).toBeInTheDocument();
  });

  it("renders nothing for empty items", () => {
    const { container } = render(<Treemap items={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing when all values are zero", () => {
    const zeroItems: TreemapItem[] = [
      { code: "005930", name: "삼성전자", value: 0, weight: 0, pnl_pct: 0 },
    ];
    const { container } = render(<Treemap items={zeroItems} />);
    expect(container.innerHTML).toBe("");
  });

  it("applies green class for positive pnl", () => {
    render(<Treemap items={[items[0]]} />);
    const cell = screen.getByText("005930").closest("div[class*='bg-']");
    expect(cell?.className).toMatch(/bg-green/);
  });

  it("applies red class for negative pnl", () => {
    render(<Treemap items={[items[1]]} />);
    const cell = screen.getByText("035420").closest("div[class*='bg-']");
    expect(cell?.className).toMatch(/bg-red/);
  });

  it("applies gray class for zero pnl", () => {
    render(<Treemap items={[items[2]]} />);
    const cell = screen.getByText("000660").closest("div[class*='bg-']");
    expect(cell?.className).toMatch(/bg-gray/);
  });
});
