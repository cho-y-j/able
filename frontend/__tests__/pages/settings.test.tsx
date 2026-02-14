import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SettingsPage from "@/app/dashboard/settings/page";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

describe("SettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default: /keys returns empty array so the component finishes loading
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

  it("renders KIS form", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Korea Investment Securities API")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("App Key")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("App Secret")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("e.g., 50123456-01")).toBeInTheDocument();
      expect(screen.getByText("Paper Trading (recommended for testing)")).toBeInTheDocument();
      expect(screen.getByText("Save KIS Credentials")).toBeInTheDocument();
    });
  });

  it("renders LLM form", async () => {
    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("LLM API Configuration")).toBeInTheDocument();
      expect(screen.getByText("Provider")).toBeInTheDocument();
      expect(screen.getByText("Model")).toBeInTheDocument();
      expect(screen.getByPlaceholderText("API Key (e.g., sk-...)")).toBeInTheDocument();
      expect(screen.getByText("Save LLM API Key")).toBeInTheDocument();
    });
  });

  it("fetches and displays saved keys on mount", async () => {
    mockedApi.get.mockImplementation((url: string) => {
      if (url === "/keys") {
        return Promise.resolve({
          data: {
            keys: [
              {
                id: "k1",
                service_type: "kis",
                provider_name: "kis",
                label: "My KIS Key",
                model_name: null,
                is_active: true,
                is_paper_trading: true,
                masked_key: "abc***xyz",
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
              },
            ],
          },
        });
      }
      return Promise.reject(new Error("Unknown endpoint"));
    });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText("Saved API Keys")).toBeInTheDocument();
      expect(screen.getByText("My KIS Key")).toBeInTheDocument();
      expect(screen.getByText("OpenAI Key")).toBeInTheDocument();
      expect(screen.getByText("abc***xyz")).toBeInTheDocument();
      expect(screen.getByText("sk-***def")).toBeInTheDocument();
      // "gpt-4o" appears both in the saved keys list and the LLM model dropdown
      const gpt4oMatches = screen.getAllByText("gpt-4o");
      expect(gpt4oMatches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("saves KIS credentials", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockResolvedValue({ data: {} });

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("App Key"), "my-app-key");
    await user.type(screen.getByPlaceholderText("App Secret"), "my-app-secret");
    await user.type(screen.getByPlaceholderText("e.g., 50123456-01"), "50123456-01");
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
      expect(screen.getByPlaceholderText("API Key (e.g., sk-...)")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("API Key (e.g., sk-...)"), "sk-test-key-123");
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
      expect(screen.getByPlaceholderText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("App Key"), "my-app-key");
    await user.type(screen.getByPlaceholderText("App Secret"), "my-app-secret");
    await user.type(screen.getByPlaceholderText("e.g., 50123456-01"), "50123456-01");
    await user.click(screen.getByText("Save KIS Credentials"));

    await waitFor(() => {
      expect(screen.getByText("KIS credentials saved successfully!")).toBeInTheDocument();
    });
  });

  it("shows error message on KIS save failure", async () => {
    const user = userEvent.setup();
    mockedApi.post.mockRejectedValue(new Error("Network error"));

    render(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText("App Key")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("App Key"), "bad-key");
    await user.type(screen.getByPlaceholderText("App Secret"), "bad-secret");
    await user.type(screen.getByPlaceholderText("e.g., 50123456-01"), "00000000-00");
    await user.click(screen.getByText("Save KIS Credentials"));

    await waitFor(() => {
      expect(screen.getByText("Failed to save KIS credentials")).toBeInTheDocument();
    });
  });
});
