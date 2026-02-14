import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LoginPage from "@/app/login/page";
import { useAuthStore } from "@/store/auth";

const mockLogin = jest.fn();
const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/store/auth", () => ({
  useAuthStore: jest.fn(),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

describe("LoginPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ login: mockLogin }),
    );
  });

  it("renders login form", () => {
    render(<LoginPage />);

    expect(screen.getByText("ABLE")).toBeInTheDocument();
    expect(screen.getByText("AI Stock Auto-Trading Platform")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter your password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log In" })).toBeInTheDocument();
  });

  it("has link to register page", () => {
    render(<LoginPage />);

    const link = screen.getByText("Register");
    expect(link).toHaveAttribute("href", "/register");
  });

  it("submits login form with credentials", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.type(screen.getByPlaceholderText("Enter your password"), "password123");
    await user.click(screen.getByRole("button", { name: "Log In" }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("test@example.com", "password123");
    });
  });

  it("redirects to dashboard on successful login", async () => {
    mockLogin.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.type(screen.getByPlaceholderText("Enter your password"), "pass");
    await user.click(screen.getByRole("button", { name: "Log In" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows error message on login failure", async () => {
    mockLogin.mockRejectedValueOnce(new Error("Invalid credentials"));
    const user = userEvent.setup();

    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "bad@example.com");
    await user.type(screen.getByPlaceholderText("Enter your password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log In" }));

    await waitFor(() => {
      expect(screen.getByText("Invalid email or password")).toBeInTheDocument();
    });
  });

  it("shows loading state during login", async () => {
    let resolveLogin: () => void;
    mockLogin.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveLogin = resolve;
      }),
    );
    const user = userEvent.setup();

    render(<LoginPage />);

    await user.type(screen.getByPlaceholderText("you@example.com"), "test@example.com");
    await user.type(screen.getByPlaceholderText("Enter your password"), "pass");
    await user.click(screen.getByRole("button", { name: "Log In" }));

    expect(screen.getByRole("button", { name: "Logging in..." })).toBeDisabled();

    resolveLogin!();
    await waitFor(() => {
      expect(screen.queryByText("Logging in...")).not.toBeInTheDocument();
    });
  });
});
