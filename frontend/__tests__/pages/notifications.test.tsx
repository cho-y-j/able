import { render, screen, waitFor } from "@testing-library/react";
import NotificationsPage from "@/app/dashboard/notifications/page";
import api from "@/lib/api";

jest.mock("@/lib/api");

const mockedApi = api as jest.Mocked<typeof api>;

describe("NotificationsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    // Default: empty notifications
    mockedApi.get.mockResolvedValue({
      data: { notifications: [], unread_count: 0, total: 0 },
    });
  });

  it("renders page title", async () => {
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("Notifications")).toBeInTheDocument();
    });
  });

  it("shows empty state", async () => {
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByText("No notifications yet.")).toBeInTheDocument();
    });
  });

  it("renders category filters", async () => {
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "All" })).toBeInTheDocument();
    });
  });

  it("shows mark all read button when unread", async () => {
    mockedApi.get.mockResolvedValue({
      data: {
        notifications: [
          {
            id: "n1",
            category: "trade",
            title: "Trade executed",
            message: "Bought 10 shares",
            is_read: false,
            data: null,
            link: null,
            created_at: new Date().toISOString(),
          },
        ],
        unread_count: 1,
        total: 1,
      },
    });

    render(<NotificationsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Mark all read" }),
      ).toBeInTheDocument();
    });
  });

  it("shows preferences button", async () => {
    render(<NotificationsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Preferences" }),
      ).toBeInTheDocument();
    });
  });
});
