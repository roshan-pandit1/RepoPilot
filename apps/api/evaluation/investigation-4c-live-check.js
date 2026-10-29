// User approved migration 0008 and one new job; run only after the host migration completes.
// Run once on the signed-in local RepoPilot origin; no cookies, tokens, issue text or snippets are printed.
(async () => {
  if (location.origin !== "http://localhost:3000") throw new Error("Open the local RepoPilot origin first");
  const part = document.cookie.split("; ").find(value => value.startsWith("rp_csrf="));
  if (!part) throw new Error("Sign in to RepoPilot first");
  const csrf = decodeURIComponent(part.slice("rp_csrf=".length));
  const repo = "1435878031";
  const index = await fetch(`/api/code/${repo}/index-status`, { cache: "no-store" });
  if (!index.ok) throw new Error(`Authorized snapshot check HTTP ${index.status}; no job submitted`);
  const snapshot = await index.json();
  if (!/^[0-9a-f]{40}$/.test(snapshot.commit_sha ?? "")) {
    throw new Error("No authorized published snapshot; no job submitted");
  }
  console.log("Authorized published snapshot commit:", snapshot.commit_sha);
  const created = await fetch(`/api/investigations/${repo}/issues/1`, {
    method: "POST", headers: { "X-CSRF-Token": csrf }, cache: "no-store",
  });
  if (created.status !== 202) throw new Error(`Submission HTTP ${created.status}`);
  const job = await created.json();
  console.log("Submitted evidence job:", { job_id: job.job_id, status: job.status });
  for (let attempt = 0; attempt < 60; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const response = await fetch(`/api/investigations/${repo}/jobs/${job.job_id}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Status HTTP ${response.status}`);
    const state = await response.json();
    if (["completed", "cancelled", "failed"].includes(state.status)) {
      console.log("Terminal state:", { job_id: state.job_id, status: state.status, attempts: state.attempts,
        operation: state.operation, snapshot_id: state.snapshot_id, commit_sha: state.commit_sha,
        retrieval_status: state.retrieval_status, evidence_count: state.evidence_count, error_code: state.error_code });
      if (state.status !== "completed") return;
      if (state.commit_sha !== snapshot.commit_sha) {
        throw new Error("Snapshot changed after preflight; inspect the existing job without resubmitting");
      }
      const evidence = await fetch(`/api/investigations/${repo}/jobs/${job.job_id}/evidence`, { cache: "no-store" });
      if (!evidence.ok) throw new Error(`Evidence HTTP ${evidence.status}`);
      const data = await evidence.json();
      console.log("Evidence references (candidates, not relevance judgments):", {
        snapshot_id: data.snapshot_id, commit_sha: data.commit_sha, count: data.evidence_count,
        retrieval_status: data.retrieval_status,
        items: data.items.map(item => ({ rank: item.rank, path: item.path, symbol: item.symbol,
          start_line: item.start_line, end_line: item.end_line, url: item.url,
          query_id: item.query_id, query_rank: item.query_rank, method: item.method }))
      });
      return;
    }
  }
  console.log("No terminal state within 120 seconds. Do not resubmit; inspect the existing job.");
})().catch(error => console.error("Verification failed:", error.message));
