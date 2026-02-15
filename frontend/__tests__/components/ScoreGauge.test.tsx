import { render, screen } from "@testing-library/react";
import ScoreGauge from "@/app/dashboard/strategies/[id]/_components/ScoreGauge";

describe("ScoreGauge", () => {
  it("renders SVG element", () => {
    const { container } = render(<ScoreGauge value={75} label="종합" />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
  });

  it("displays the numeric value", () => {
    render(<ScoreGauge value={82} label="WFA" />);
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("displays the label", () => {
    render(<ScoreGauge value={65} label="MC" />);
    expect(screen.getByText("MC")).toBeInTheDocument();
  });

  it("displays grade A for value >= 80", () => {
    render(<ScoreGauge value={85} label="Test" />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("displays grade B+ for value >= 70", () => {
    render(<ScoreGauge value={72} label="Test" />);
    expect(screen.getByText("B+")).toBeInTheDocument();
  });

  it("displays grade D for low value", () => {
    render(<ScoreGauge value={25} label="Test" />);
    expect(screen.getByText("D")).toBeInTheDocument();
  });

  it("shows N/A when value is null", () => {
    render(<ScoreGauge value={null} label="OOS" />);
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(screen.getByText("OOS")).toBeInTheDocument();
  });

  it("renders two circle elements (background + foreground) when value is present", () => {
    const { container } = render(<ScoreGauge value={60} label="Test" />);
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBe(2);
  });

  it("renders only background circle when value is null", () => {
    const { container } = render(<ScoreGauge value={null} label="Test" />);
    const circles = container.querySelectorAll("circle");
    expect(circles.length).toBe(1);
  });

  it("respects custom size prop", () => {
    const { container } = render(<ScoreGauge value={50} label="Test" size={120} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("120");
    expect(svg?.getAttribute("height")).toBe("120");
  });

  it("respects custom max prop", () => {
    render(<ScoreGauge value={80} max={200} label="Test" />);
    // 80/200 = 40% → grade C
    expect(screen.getByText("C")).toBeInTheDocument();
  });
});
