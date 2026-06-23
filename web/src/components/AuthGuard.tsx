/**
 * Auth guard — redirects unauthenticated users to login,
 * and checks role access for protected routes.
 */
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import type { UserRole } from "../hooks/useAuth";

interface AuthGuardProps {
  children: ReactNode;
  role: UserRole;
  allowedRoles: UserRole[];
  isAuthenticated: boolean;
  loading: boolean;
}

export function AuthGuard({
  children,
  role,
  allowedRoles,
  isAuthenticated,
  loading,
}: AuthGuardProps) {
  if (loading) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (role && !allowedRoles.includes(role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
}
