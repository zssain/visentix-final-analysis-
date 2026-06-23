/**
 * AuthGuard + role routing tests.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AuthGuard } from "../components/AuthGuard";

function renderGuard(
  isAuthenticated: boolean,
  role: "customer" | "sme" | "admin" | null,
  allowedRoles: ("customer" | "sme" | "admin" | null)[],
) {
  return render(
    <MemoryRouter>
      <AuthGuard
        isAuthenticated={isAuthenticated}
        role={role}
        allowedRoles={allowedRoles}
        loading={false}
      >
        <div data-testid="protected">Protected Content</div>
      </AuthGuard>
    </MemoryRouter>,
  );
}

describe("AuthGuard", () => {
  it("shows loading state", () => {
    render(
      <MemoryRouter>
        <AuthGuard isAuthenticated={false} role={null} allowedRoles={["customer"]} loading={true}>
          <div>Content</div>
        </AuthGuard>
      </MemoryRouter>,
    );
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("redirects unauthenticated users to login", () => {
    renderGuard(false, null, ["customer"]);
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("shows content for authenticated user with correct role", () => {
    renderGuard(true, "customer", ["customer", "sme", "admin"]);
    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });

  it("redirects user with wrong role to unauthorized", () => {
    renderGuard(true, "customer", ["admin"]);
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("allows admin to access admin routes", () => {
    renderGuard(true, "admin", ["admin"]);
    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });

  it("allows sme to access sme routes", () => {
    renderGuard(true, "sme", ["sme", "admin"]);
    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });

  it("blocks customer from admin routes", () => {
    renderGuard(true, "customer", ["admin"]);
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("blocks customer from sme routes", () => {
    renderGuard(true, "customer", ["sme", "admin"]);
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("allows admin to access customer routes", () => {
    renderGuard(true, "admin", ["customer", "sme", "admin"]);
    expect(screen.getByTestId("protected")).toBeInTheDocument();
  });
});
