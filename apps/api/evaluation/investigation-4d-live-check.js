// Run once only after the approved migration 0009 and all disposable PostgreSQL checks pass.
// Paste into the signed-in local application's console; never print credentials or issue/source text.
(async () => {
  if (location.origin !== "http://localhost:3000") throw new Error("Open the local RepoPilot origin first");
  const part = document.cookie.split("; ").find(value => value.startsWith("rp_csrf="));
  if (!part) throw new Error("Sign in to RepoPilot first");
  const csrf = decodeURIComponent(part.slice("rp_csrf=".length));
  const repo = "1435878031";
  const parent = "457d40bf-7e15-4e10-9a27-b8a0de9e513b";
  const base = `/api/investigations/${repo}/jobs/${parent}`;
  const beforeResponse = await fetch(base, { cache: "no-store" });
  if (!beforeResponse.ok) throw new Error(`Parent preflight HTTP ${beforeResponse.status}; no task submitted`);
  const before = await beforeResponse.json();
  if (before.job_id !== parent || before.status !== "completed" || before.operation !== "code_evidence" || before.attempts !== 1 ||
      before.snapshot_id !== "24e51533-c612-4833-921d-447cfed7df99" ||
      before.commit_sha !== "63491908290e6874dbaaf2b15c2a96473aad1324") {
    throw new Error("The original completed 4C investigation changed; no task submitted");
  }
  const evidenceResponse = await fetch(`${base}/evidence`, { cache: "no-store" });
  if (!evidenceResponse.ok) throw new Error(`Evidence preflight HTTP ${evidenceResponse.status}; no task submitted`);
  const evidence = await evidenceResponse.json();
  if (evidence.snapshot_id !== "24e51533-c612-4833-921d-447cfed7df99" ||
      evidence.commit_sha !== "63491908290e6874dbaaf2b15c2a96473aad1324" || evidence.evidence_count !== 20 ||
      !Array.isArray(evidence.items) || evidence.items.length !== 20) {
    throw new Error("The authorized snapshot or evidence changed; no task submitted");
  }
  const existing = await fetch(`${base}/report`, { cache: "no-store" });
  if (existing.status !== 404) throw new Error(`Report preflight HTTP ${existing.status}; no task submitted`);
  const response = await fetch(`${base}/report`, {
    method: "POST", headers: { "X-CSRF-Token": csrf }, cache: "no-store",
  });
  if (response.status !== 202) throw new Error(`Report submission HTTP ${response.status}; do not resubmit`);
  const submitted = await response.json();
  console.log("Submitted mock report task:", { report_job_id: submitted.report_job_id, status: submitted.status });
  for (let attempt = 0; attempt < 60; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const polled = await fetch(`${base}/report`, { cache: "no-store" });
    if (!polled.ok) throw new Error(`Report status HTTP ${polled.status}; do not resubmit`);
    const result = await polled.json();
    if (["completed", "cancelled", "failed"].includes(result.status)) {
      const report = result.report;
      if (result.status === "completed") {
        if (!report || report.investigation_id !== parent || report.repository_id !== repo ||
            report.snapshot_id !== evidence.snapshot_id || report.commit_sha !== evidence.commit_sha ||
            report.provider !== "mock" || report.model !== "deterministic-v1" || report.status !== "completed") {
          throw new Error("The completed report identity or provider did not match; inspect the existing task");
        }
        const byId = new Map(evidence.items.map(item => [item.chunk_id, item]));
        const references = report.hypotheses.flatMap(h => [...h.evidence, ...h.contradictory_evidence]);
        if (!references.length || references.some(ref => {
          const item = byId.get(ref.chunk_id);
          return !item || ref.snapshot_id !== evidence.snapshot_id || ref.commit_sha !== evidence.commit_sha ||
            ref.path !== item.path || ref.symbol !== item.symbol || ref.start_line !== item.start_line ||
            ref.end_line !== item.end_line || ref.url !== item.url;
        })) throw new Error("Report citations failed comparison to the authorized evidence; inspect the existing task");
        const afterResponse = await fetch(base, { cache: "no-store" });
        if (!afterResponse.ok) throw new Error(`Parent recheck HTTP ${afterResponse.status}; inspect the existing task`);
        const after = await afterResponse.json();
        const fields = ["job_id", "status", "operation", "attempts", "created_at", "updated_at", "started_at", "completed_at", "snapshot_id", "commit_sha"];
        if (fields.some(field => before[field] !== after[field])) {
          throw new Error("The original 4C investigation changed; inspect the existing task");
        }
        console.log("Validated authorized report references:", references.length,
          "matched persisted evidence; original 4C job state unchanged.");
      }
      console.log("Terminal mock report state:", {
        report_job_id: result.report_job_id, status: result.status, attempts: result.attempts,
        error_code: result.error_code, snapshot_id: report?.snapshot_id, commit_sha: report?.commit_sha,
        provider: report?.provider, model: report?.model, disclaimer: report?.disclaimer,
        hypothesis_count: report?.hypotheses.length,
        citation_count: report?.hypotheses.reduce((count, h) => count + h.evidence.length + h.contradictory_evidence.length, 0),
      });
      return;
    }
  }
  console.log("No terminal state within 120 seconds. Do not resubmit; inspect the existing task.");
})().catch(error => console.error("Verification failed:", error.message));
