import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "@/app/register/page";
import { useAuthStore } from "@/store/auth";

const mockRegister = jest.fn();
const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

jest.mock("@/store/auth", () => ({
  useAuthStore: jest.fn(),
}));

const mockedUseAuthStore = useAuthStore as unknown as jest.Mock;

function getFormInputs() {
  const nameInput = screen.getByPlaceholderText("Your name");
  const form = nameInput.closest("form")!;
  const allInputs = form.querySelectorAll("input");
  return {
    name: allInputs[0] as HTMLInputElement,
    email: allInputs[1] as HTMLInputElement,
    password: allInputs[2] as HTMLInputElement,
  };
}

describe("RegisterPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedUseAuthStore.mockImplementation((selector: (s: unknown) => unknown) =>
      selector({ register: mockRegister }),
    );
  });

  it("renders registration form", () => {
    render(<RegisterPage />);

    expect(screen.getByRole("heading", { name: "Create Account" })).toBeInTheDocument();
    expect(screen.getByText("Start AI-powered stock trading")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Your name")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Account" })).toBeInTheDocument();
  });

  it("has link to login page", () => {
    render(<RegisterPage />);

    const link = screen.getByText("Log In");
    expect(link).toHaveAttribute("href", "/login");
  });

  it("has three input fields (name, email, password)", () => {
    render(<RegisterPage />);

    const { name, email, password } = getFormInputs();
    expect(name.type).toBe("text");
    expect(email.type).toBe("email");
    expect(password.type).toBe("password");
  });

  it("submits with name, email, and password", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    render(<RegisterPage />);

    const inputs = getFormInputs();
    await user.type(inputs.name, "Trader Kim");
    await user.type(inputs.email, "kim@example.com");
    await user.type(inputs.password, "securepass1");
    await user.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith("kim@example.com", "securepass1", "Trader Kim");
    });
  });

  it("sends undefined display name when empty", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    render(<RegisterPage />);

    const inputs = getFormInputs();
    await user.type(inputs.email, "anon@example.com");
    await user.type(inputs.password, "password1");
    await user.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith("anon@example.com", "password1", undefined);
    });
  });

  it("redirects to settings page on success", async () => {
    mockRegister.mockResolvedValueOnce(undefined);
    const user = userEvent.setup();

    render(<RegisterPage />);

    const inputs = getFormInputs();
    await user.type(inputs.email, "new@test.com");
    await user.type(inputs.password, "password1");
    await user.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard/settings");
    });
  });

  it("shows error message on registration failure", async () => {
    mockRegister.mockRejectedValueOnce(new Error("Email taken"));
    const user = userEvent.setup();

    render(<RegisterPage />);

    const inputs = getFormInputs();
    await user.type(inputs.email, "taken@test.com");
    await user.type(inputs.password, "password1");
    await user.click(screen.getByRole("button", { name: "Create Account" }));

    await waitFor(() => {
      expect(screen.getByText("Registration failed. Email may already be in use.")).toBeInTheDocument();
    });
  });

  it("shows loading state during registration", async () => {
    let resolveRegister: () => void;
    mockRegister.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveRegister = resolve;
      }),
    );
    const user = userEvent.setup();

    render(<RegisterPage />);

    const inputs = getFormInputs();
    await user.type(inputs.email, "new@test.com");
    await user.type(inputs.password, "password1");
    await user.click(screen.getByRole("button", { name: "Create Account" }));

    expect(screen.getByRole("button", { name: "Creating..." })).toBeDisabled();

    resolveRegister!();
    await waitFor(() => {
      expect(screen.queryByText("Creating...")).not.toBeInTheDocument();
    });
  });
});
