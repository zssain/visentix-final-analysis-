import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export function AdminConsole() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.get("/admin/training-stats").then(setStats).catch(console.error);
  }, []);

  return (
    <div>
      <h2>Admin Console</h2>
      <h3>Training Label Stats</h3>
      {stats ? (
        <pre>{JSON.stringify(stats, null, 2)}</pre>
      ) : (
        <p>Loading stats...</p>
      )}
      <h3>Actions</h3>
      <button onClick={() => api.post("/admin/trigger-assessment")}>
        Trigger Assessment
      </button>
    </div>
  );
}
