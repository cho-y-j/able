import { render, screen } from "@testing-library/react";
import { GradeBadge, gradeInfo } from "@/app/dashboard/strategies/_components/GradeBadge";

describe("gradeInfo", () => {
  it("returns A+ for score >= 90", () => {
    const info = gradeInfo(95);
    expect(info.grade).toBe("A+");
    expect(info.bg).toContain("green");
  });

  it("returns A for score >= 80", () => {
    expect(gradeInfo(85).grade).toBe("A");
  });

  it("returns B+ for score >= 70", () => {
    expect(gradeInfo(72).grade).toBe("B+");
  });

  it("returns B for score >= 60", () => {
    expect(gradeInfo(63).grade).toBe("B");
  });

  it("returns C+ for score >= 50", () => {
    expect(gradeInfo(55).grade).toBe("C+");
  });

  it("returns C for score >= 40", () => {
    expect(gradeInfo(45).grade).toBe("C");
  });

  it("returns D for score < 40", () => {
    const info = gradeInfo(30);
    expect(info.grade).toBe("D");
    expect(info.bg).toContain("red");
  });

  it("returns dash for null score", () => {
    const info = gradeInfo(null);
    expect(info.grade).toBe("-");
    expect(info.label).toBe("미평가");
  });
});

describe("GradeBadge component", () => {
  it("renders grade text for a given score", () => {
    render(<GradeBadge score={85} />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("renders dash for null score", () => {
    render(<GradeBadge score={null} />);
    expect(screen.getByText("-")).toBeInTheDocument();
  });

  it("renders sm size by default", () => {
    const { container } = render(<GradeBadge score={90} />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.tagName).toBe("SPAN");
    expect(badge.className).toContain("text-xs");
  });

  it("renders md size", () => {
    const { container } = render(<GradeBadge score={90} size="md" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.tagName).toBe("SPAN");
    expect(badge.className).toContain("text-sm");
  });

  it("renders lg size as circular div", () => {
    const { container } = render(<GradeBadge score={90} size="lg" />);
    const badge = container.firstChild as HTMLElement;
    expect(badge.tagName).toBe("DIV");
    expect(badge.className).toContain("rounded-full");
    expect(badge.className).toContain("w-12");
  });

  it("shows correct grade for boundary score 80", () => {
    render(<GradeBadge score={80} />);
    expect(screen.getByText("A")).toBeInTheDocument();
  });

  it("shows D grade for low score", () => {
    render(<GradeBadge score={10} />);
    expect(screen.getByText("D")).toBeInTheDocument();
  });
});
