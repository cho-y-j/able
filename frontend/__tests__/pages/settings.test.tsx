import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPage from "@/app/dashboard/settings/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

const mockKeys = [
  {
    id: "k1",
    service_type: "kis",
    provider_name: "kis",
    label: "My KIS Key",
    model_name: null,
    is_active: true,
    is_paper_trading: true,
    masked_key: "abc***xyz",
    last_validated_at: new Date(Date.now() - 3600000).toISOString(), // 1h ago
    account_number: "50123456-01",
  },
  {
    id: "k2",
    service_type: "llm",
    provider_name: "openai",
    label: "OpenAI Key",
    model_name: "gpt-4o",
    is_active: true,
    is_paper_trading: false,
    masked_key: "sk-***def",
    last_validated_at: null,
    account_number: null,
  },
];

describe("SettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.confirm = jest.fn(() => true);

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") {
        return Promise.resolve({ data: { keys: [] } });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    mockedApi.post.mockResolvedValue({ data: {} });
    mockedApi.delete.mockResolvedValue({ data: {} });
  });

  it("renders settings title", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Settings")).toBeInTheDocument();
    });
  });

  it("renders KIS form with i18n labels", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Korea Investment Securities API")).toBeInTheDocument();
      expect(screen.getByLabelText("App Key")).toBeInTheDocument();
      expect(screen.getByLabelText("App Secret")).toBeInTheDocument();
      expect(screen.getByText("Paper Trading (recommended for testing)")).toBeInTheDocument();
    });
  });

  it("renders LLM form", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("LLM API Configuration")).toBeInTheDocument();
      expect(screen.getByText("Provider")).toBeInTheDocument();
      expect(screen.getByText("Model")).toBeInTheDocument();
    });
  });

  it("shows no keys message when empty", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("No saved keys. Register API keys below.")).toBeInTheDocument();
    });
  });

  it("fetches and displays saved keys on mount", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: mockKeys } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Saved API Keys")).toBeInTheDocument();
      expect(screen.getByText("My KIS Key")).toBeInTheDocument();
      expect(screen.getByText("OpenAI Key")).toBeInTheDocument();
      expect(screen.getByText("abc***xyz")).toBeInTheDocument();
      expect(screen.getByText("sk-***def")).toBeInTheDocument();
    });
  });

  it("shows account number for KIS keys", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: mockKeys } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Account: 50123456-01/)).toBeInTheDocument();
    });
  });

  it("shows verified status with relative time", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: mockKeys } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Verified/)).toBeInTheDocument();
      expect(screen.getByText(/1h ago/)).toBeInTheDocument();
    });
  });

  it("shows not verified status", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: mockKeys } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Not verified")).toBeInTheDocument();
    });
  });

  it("shows Test Connection button for each key", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: mockKeys } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      const buttons = screen.getAllByText("Test Connection");
      expect(buttons).toHaveLength(2);
    });
  });

  it("saves KIS credentials", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("App Key"), "my-app-key");
    await user.type(screen.getByLabelText("App Secret"), "my-app-secret");
    await user.type(screen.getByLabelText("Account Number"), "50123456-01");
    await user.click(screen.getByText("Save KIS Credentials"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/keys/kis", {
        app_key: "my-app-key",
        app_secret: "my-app-secret",
        account_number: "50123456-01",
        is_paper_trading: true,
      });
    });
  });

  it("saves LLM credentials", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText(/API Key/)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/API Key/), "sk-test-key-123");
    await user.click(screen.getByText("Save LLM API Key"));

    await waitFor(() => {
      expect(mockedApi.post).toHaveBeenCalledWith("/keys/llm", {
        provider_name: "openai",
        api_key: "sk-test-key-123",
        model_name: "gpt-4o",
      });
    });
  });

  it("shows success message on KIS save", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("App Key"), "my-app-key");
    await user.type(screen.getByLabelText("App Secret"), "my-app-secret");
    await user.type(screen.getByLabelText("Account Number"), "50123456-01");
    await user.click(screen.getByText("Save KIS Credentials"));

    await waitFor(() => {
      expect(screen.getByText(/KIS credentials saved successfully/)).toBeInTheDocument();
    });
  });

  it("shows error message on KIS save failure", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockRejectedValue({
      response: { data: { detail: "Invalid credentials" } },
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByLabelText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("App Key"), "bad-key");
    await user.type(screen.getByLabelText("App Secret"), "bad-secret");
    await user.type(screen.getByLabelText("Account Number"), "00000000-00");
    await user.click(screen.getByText("Save KIS Credentials"));

    await waitFor(() => {
      expect(screen.getByText(/Failed to save KIS credentials/)).toBeInTheDocument();
    });
  });

  it("confirms before deleting a key", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: [mockKeys[0]] } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("My KIS Key")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));

    expect(window.confirm).toHaveBeenCalledWith("Are you sure you want to delete this API key?");
    expect(mockedApi.delete).toHaveBeenCalledWith("/keys/k1");
  });

  it("does not delete when confirm is cancelled", async () => {
    (window.confirm as jest.Mock).mockReturnValueOnce(false);

    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") return Promise.resolve({ data: { keys: [mockKeys[0]] } });
      return Promise.reject(new Error("Unknown endpoint"));
    });

    const user = userEvent.setup();
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("My KIS Key")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));

    expect(window.confirm).toHaveBeenCalled();
    expect(mockedApi.delete).not.toHaveBeenCalled();
  });
});
