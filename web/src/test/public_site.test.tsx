import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";

beforeEach(() => {
  localStorage.clear();
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  vi.stubGlobal("fetch", vi.fn(async () => new Response("[]", { status: 503 })));
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function open(path: string, role?: string) {
  window.history.replaceState({}, "", path);
  if (role) {
    localStorage.setItem("visentix-auth-session", JSON.stringify({ access_token: "test-only", user: { id: "test", email: "test@example.invalid" } }));
    localStorage.setItem("visentix-auth-profile", JSON.stringify({ role, organizationId: null }));
  }
  return render(<App />);
}

describe("F08 public website in the actual application router", () => {
  it.each(["/", "/platform", "/solutions", "/solutions/notice-assessment", "/solutions/quarterly-report", "/resources", "/about", "/contact", "/pricing", "/solutions/continuous-monitoring", "/solutions/white-label"])("%s is public and independent of the backend", async path => {
    const { container } = open(path);
    expect(screen.getByRole("navigation", { name: "Website" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(window.location.pathname).toBe(path);
    expect(screen.queryByRole("navigation", { name: "Main navigation" })).not.toBeInTheDocument();
    expect(container.querySelector('a[href="#"]')).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("website login reaches the existing login form", async () => {
    open("/");
    await userEvent.click(screen.getByRole("link", { name: "Log in" }));
    expect(await screen.findByLabelText("Email address")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
  });

  it("signed-in visitors retain the public layout and can open their workspace", async () => {
    open("/", "customer");
    expect(screen.queryByRole("navigation", { name: "Main navigation" })).not.toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("banner")).getByRole("link", { name: "Open workspace" }));
    await waitFor(() => expect(window.location.pathname).toBe("/assessments"));
    expect(screen.getByRole("heading", { name: "Your Assessments" })).toBeInTheDocument();
  });

  it.each([["customer", "/assessments"], ["sme", "/workbench"], ["admin", "/admin"]])("workspace preserves the %s landing", async (role, landing) => {
    open("/workspace", role);
    await waitFor(() => expect(window.location.pathname).toBe(landing));
  });

  it("workspace still requires authentication", async () => {
    open("/workspace");
    await waitFor(() => expect(window.location.pathname).toBe("/login"));
  });

  it("a customer cannot reach the admin surface through the website integration", async () => {
    open("/admin", "customer");
    await waitFor(() => expect(window.location.pathname).toBe("/unauthorized"));
  });

  it("keeps completed background work visible on public pages when signed in", () => {
    localStorage.setItem("visentix.tasks.v1", JSON.stringify([{
      taskId: "finished-fixture", kind: "intake", label: "Finished assessment",
      status: "ready", stage: "ready", submittedAt: Date.now(), dismissed: false,
    }]));
    open("/", "customer");
    expect(screen.getByRole("complementary", { name: "Background task progress" })).toBeInTheDocument();
    expect(screen.getByText("Finished assessment")).toBeInTheDocument();
  });

  it("contact collects no personal data and never claims a message was sent", () => {
    const { container } = open("/contact");
    expect(screen.getByText("Online enquiries are not available yet")).toBeInTheDocument();
    expect(container.querySelector("form")).toBeNull();
    expect(screen.queryByText("Message received.")).not.toBeInTheDocument();
  });
});
