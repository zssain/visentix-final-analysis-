import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export function CustomerDashboard() {
  const [assessments, setAssessments] = useState<unknown[]>([]);

  useEffect(() => {
    api.get("/assessments/").then(setAssessments).catch(console.error);
  }, []);

  return (
    <div>
      <h2>My Assessments</h2>
      <p>{Array.isArray(assessments) ? assessments.length : 0} assessments</p>
    </div>
  );
}
