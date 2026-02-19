import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StockAutocomplete } from "@/components/StockAutocomplete";

// Mock the useStockSearch hook
const mockResults = [
  { code: "003570", name: "SNT다이내믹스", market: "KOSPI", sector: "기계" },
  { code: "036530", name: "SNT홀딩스", market: "KOSPI", sector: "지주회사" },
  { code: "064960", name: "SNT모티브", market: "KOSPI", sector: "자동차부품" },
];

let mockLoading = false;
let capturedQuery = "";
let capturedMarket = "";

jest.mock("@/lib/useStockSearch", () => ({
  useStockSearch: (query: string, market: string) => {
    capturedQuery = query;
    capturedMarket = market;
    return {
      results: query.length > 0 ? mockResults : [],
      loading: mockLoading,
    };
  },
  __esModule: true,
}));

describe("StockAutocomplete", () => {
  const mockOnChange = jest.fn();
  const mockOnSelect = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockLoading = false;
    capturedQuery = "";
    capturedMarket = "";
  });

  it("renders input with placeholder", () => {
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
        placeholder="종목 검색"
      />
    );
    expect(screen.getByPlaceholderText("종목 검색")).toBeInTheDocument();
  });

  it("renders default placeholder when none provided", () => {
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );
    expect(
      screen.getByPlaceholderText("종목코드 또는 종목명")
    ).toBeInTheDocument();
  });

  it("shows dropdown when results are available after typing", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      expect(screen.getByText("SNT다이내믹스")).toBeInTheDocument();
      expect(screen.getByText("SNT홀딩스")).toBeInTheDocument();
      expect(screen.getByText("SNT모티브")).toBeInTheDocument();
    });
  });

  it("displays stock code next to name", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      expect(screen.getByText("003570")).toBeInTheDocument();
      expect(screen.getByText("036530")).toBeInTheDocument();
    });
  });

  it("displays market badges (KOSPI/KOSDAQ)", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      const kospiBadges = screen.getAllByText("KOSPI");
      expect(kospiBadges.length).toBe(3);
    });
  });

  it("calls onChange when typing", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "삼성");
    expect(mockOnChange).toHaveBeenCalled();
  });

  it("calls onSelect and sets code when stock is clicked", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      expect(screen.getByText("SNT다이내믹스")).toBeInTheDocument();
    });

    await user.click(screen.getByText("SNT다이내믹스"));

    expect(mockOnSelect).toHaveBeenCalledWith(mockResults[0]);
    expect(mockOnChange).toHaveBeenCalledWith("003570");
  });

  it("passes market parameter to hook", () => {
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
        market="us"
      />
    );
    expect(capturedMarket).toBe("us");
  });

  it("defaults market to kr", () => {
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );
    expect(capturedMarket).toBe("kr");
  });

  it("shows loading spinner when searching", async () => {
    mockLoading = true;
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "s");

    // The spinner div should be present
    const container = screen.getByRole("textbox").parentElement;
    expect(container?.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("closes dropdown when clicking outside", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <div>
        <StockAutocomplete
          value=""
          onChange={mockOnChange}
          onSelect={mockOnSelect}
        />
        <div data-testid="outside">Outside</div>
      </div>
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      expect(screen.getByText("SNT다이내믹스")).toBeInTheDocument();
    });

    await user.click(screen.getByTestId("outside"));

    await waitFor(() => {
      expect(screen.queryByText("SNT다이내믹스")).not.toBeInTheDocument();
    });
  });

  it("shows sector info in dropdown items", async () => {
    const user = userEvent.setup();
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
      />
    );

    await user.type(screen.getByRole("textbox"), "snt");

    await waitFor(() => {
      expect(screen.getByText("기계")).toBeInTheDocument();
      expect(screen.getByText("지주회사")).toBeInTheDocument();
    });
  });

  it("applies custom className", () => {
    render(
      <StockAutocomplete
        value=""
        onChange={mockOnChange}
        onSelect={mockOnSelect}
        className="custom-class"
      />
    );
    expect(screen.getByRole("textbox")).toHaveClass("custom-class");
  });
});
