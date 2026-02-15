import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecipeCard from "@/app/dashboard/recipes/_components/RecipeCard";

const mockRecipe = {
  id: "r1",
  name: "MACD + RSI 보수적",
  description: "보수적 매매 전략",
  signal_config: {
    combinator: "AND" as const,
    signals: [
      { type: "recommended", strategy_type: "macd_crossover", params: {}, weight: 1.0 },
      { type: "recommended", strategy_type: "rsi_mean_reversion", params: {}, weight: 0.8 },
    ],
  },
  custom_filters: {},
  stock_codes: ["005930", "000660", "035720", "051910"],
  risk_config: { stop_loss: 3, take_profit: 5, position_size: 10 },
  is_active: true,
  is_template: false,
  created_at: "2026-02-01T00:00:00Z",
  updated_at: "2026-02-01T00:00:00Z",
};

describe("RecipeCard", () => {
  const mockOnClick = jest.fn();
  const mockOnActivate = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders recipe name and description", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("MACD + RSI 보수적")).toBeInTheDocument();
    expect(screen.getByText("보수적 매매 전략")).toBeInTheDocument();
  });

  it("shows signal count and combinator badges", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("2개 시그널")).toBeInTheDocument();
    expect(screen.getByText("AND")).toBeInTheDocument();
  });

  it("displays up to 3 stock codes with overflow", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("005930")).toBeInTheDocument();
    expect(screen.getByText("000660")).toBeInTheDocument();
    expect(screen.getByText("035720")).toBeInTheDocument();
    expect(screen.queryByText("051910")).not.toBeInTheDocument();
    expect(screen.getByText("+1")).toBeInTheDocument();
  });

  it("shows stop button for active recipe", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("중지")).toBeInTheDocument();
  });

  it("shows activate button for inactive recipe", () => {
    const inactiveRecipe = { ...mockRecipe, is_active: false };
    render(
      <RecipeCard
        recipe={inactiveRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("활성화")).toBeInTheDocument();
  });

  it("calls onClick when card is clicked", async () => {
    const user = userEvent.setup();
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    await user.click(screen.getByText("MACD + RSI 보수적"));
    expect(mockOnClick).toHaveBeenCalled();
  });

  it("calls onActivate when activate button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    await user.click(screen.getByText("중지"));
    expect(mockOnActivate).toHaveBeenCalled();
    // Should not trigger card onClick
    expect(mockOnClick).not.toHaveBeenCalled();
  });

  it("calls onDelete when delete button is clicked", async () => {
    const user = userEvent.setup();
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    await user.click(screen.getByText("삭제"));
    expect(mockOnDelete).toHaveBeenCalled();
    expect(mockOnClick).not.toHaveBeenCalled();
  });

  it("renders date in Korean locale", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    // Korean date format: 2026. 2. 1.
    expect(screen.getByText(/2026/)).toBeInTheDocument();
  });

  it("shows template badge for template recipe", () => {
    const templateRecipe = { ...mockRecipe, is_template: true };
    render(
      <RecipeCard
        recipe={templateRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByText("템플릿")).toBeInTheDocument();
  });

  it("has proper aria-labels on action buttons", () => {
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    expect(screen.getByLabelText("레시피 중지")).toBeInTheDocument();
    expect(screen.getByLabelText("레시피 삭제")).toBeInTheDocument();
  });

  it("supports keyboard navigation", async () => {
    const user = userEvent.setup();
    render(
      <RecipeCard
        recipe={mockRecipe}
        onClick={mockOnClick}
        onActivate={mockOnActivate}
        onDelete={mockOnDelete}
      />
    );

    const card = screen.getByRole("button", { name: /MACD/i });
    card.focus();
    await user.keyboard("{Enter}");
    expect(mockOnClick).toHaveBeenCalled();
  });
});
