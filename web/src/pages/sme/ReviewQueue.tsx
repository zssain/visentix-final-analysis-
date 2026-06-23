import { useEffect, useState } from "react";
import { api } from "../../lib/api";

export function ReviewQueue() {
  const [queue, setQueue] = useState<unknown[]>([]);

  useEffect(() => {
    api.get("/review/queue").then(setQueue).catch(console.error);
  }, []);

  return (
    <div>
      <h2>SME Review Queue</h2>
      <p>{Array.isArray(queue) ? queue.length : 0} pending reviews</p>
    </div>
  );
}
