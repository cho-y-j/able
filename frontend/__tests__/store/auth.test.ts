import { useAuthStore } from "@/store/auth";
import api from "@/lib/api";

jest.mock("@/lib/api");
const mockedApi = api as jest.Mocked<typeof api>;

describe("useAuthStore", () => {
  beforeEach(() => {
    // Reset store between tests
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
    localStorage.clear();
    jest.clearAllMocks();
  });

  describe("initial state", () => {
    it("starts with unauthenticated state", () => {
      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });

  describe("login", () => {
    it("stores tokens and fetches user on success", async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: "acc-123", refresh_token: "ref-456" },
      });
      mockedApi.get.mockResolvedValueOnce({
        data: { id: "u1", email: "test@example.com", display_name: "Trader", is_active: true, is_verified: true },
      });

      await useAuthStore.getState().login("test@example.com", "password123");

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.token).toBe("acc-123");
      expect(state.user?.email).toBe("test@example.com");
      expect(localStorage.setItem).toHaveBeenCalledWith("access_token", "acc-123");
      expect(localStorage.setItem).toHaveBeenCalledWith("refresh_token", "ref-456");
    });

    it("calls correct API endpoints", async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: "tok", refresh_token: "ref" },
      });
      mockedApi.get.mockResolvedValueOnce({
        data: { id: "u1", email: "a@b.com", display_name: null, is_active: true, is_verified: false },
      });

      await useAuthStore.getState().login("a@b.com", "pass");

      expect(mockedApi.post).toHaveBeenCalledWith("/auth/login", { email: "a@b.com", password: "pass" });
      expect(mockedApi.get).toHaveBeenCalledWith("/auth/me");
    });
  });

  describe("register", () => {
    it("stores tokens and fetches user on success", async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: "acc-new", refresh_token: "ref-new" },
      });
      mockedApi.get.mockResolvedValueOnce({
        data: { id: "u2", email: "new@test.com", display_name: "NewUser", is_active: true, is_verified: false },
      });

      await useAuthStore.getState().register("new@test.com", "password123", "NewUser");

      const state = useAuthStore.getState();
      expect(state.isAuthenticated).toBe(true);
      expect(state.user?.display_name).toBe("NewUser");
    });

    it("sends display_name in request", async () => {
      mockedApi.post.mockResolvedValueOnce({
        data: { access_token: "t", refresh_token: "r" },
      });
      mockedApi.get.mockResolvedValueOnce({
        data: { id: "u3", email: "x@y.com", display_name: "Name", is_active: true, is_verified: false },
      });

      await useAuthStore.getState().register("x@y.com", "pass", "Name");

      expect(mockedApi.post).toHaveBeenCalledWith("/auth/register", {
        email: "x@y.com",
        password: "pass",
        display_name: "Name",
      });
    });
  });

  describe("logout", () => {
    it("clears state and localStorage", () => {
      useAuthStore.setState({
        user: { id: "u1", email: "a@b.com", display_name: null, is_active: true, is_verified: true },
        token: "tok",
        isAuthenticated: true,
      });

      useAuthStore.getState().logout();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.token).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(localStorage.removeItem).toHaveBeenCalledWith("access_token");
      expect(localStorage.removeItem).toHaveBeenCalledWith("refresh_token");
    });
  });

  describe("fetchUser", () => {
    it("fetches and sets user data", async () => {
      mockedApi.get.mockResolvedValueOnce({
        data: { id: "u1", email: "a@b.com", display_name: "Trader", is_active: true, is_verified: true },
      });

      await useAuthStore.getState().fetchUser();

      const state = useAuthStore.getState();
      expect(state.user?.email).toBe("a@b.com");
      expect(state.isAuthenticated).toBe(true);
      expect(state.isLoading).toBe(false);
    });

    it("clears auth state on API error", async () => {
      useAuthStore.setState({ isAuthenticated: true });
      mockedApi.get.mockRejectedValueOnce(new Error("401"));

      await useAuthStore.getState().fetchUser();

      const state = useAuthStore.getState();
      expect(state.user).toBeNull();
      expect(state.isAuthenticated).toBe(false);
      expect(state.isLoading).toBe(false);
    });

    it("sets isLoading during fetch", async () => {
      let resolvePromise: (value: unknown) => void;
      mockedApi.get.mockReturnValueOnce(
        new Promise((resolve) => {
          resolvePromise = resolve;
        }) as never,
      );

      const fetchPromise = useAuthStore.getState().fetchUser();
      expect(useAuthStore.getState().isLoading).toBe(true);

      resolvePromise!({ data: { id: "u1", email: "a@b.com", display_name: null, is_active: true, is_verified: true } });
      await fetchPromise;
      expect(useAuthStore.getState().isLoading).toBe(false);
    });
  });
});
