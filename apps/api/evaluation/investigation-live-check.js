// Run only on the signed-in local RepoPilot origin after the database migration is approved.
// This prints job identifiers and status only; it never prints cookies, CSRF values or issue text.
(async () => {
  if (location.origin !== "http://localhost:3000") throw new Error("Open the local RepoPilot origin first");
  const csrfPart = document.cookie.split("; ").find(value => value.startsWith("rp_csrf="));
  if (!csrfPart) throw new Error("Sign in to RepoPilot first");
  const csrf = decodeURIComponent(csrfPart.slice("rp_csrf=".length));
  const repo = "1435878031";
  const create = await fetch(`/api/investigations/${repo}/issues/1`, {
    method: "POST", headers: { "X-CSRF-Token": csrf }, cache: "no-store",
  });
  if (create.status !== 202) throw new Error(`Submission HTTP ${create.status}`);
  const data = await create.json();
  console.log("Submitted mock investigation:", { job_id: data.job_id, status: data.status });
  for (let attempt = 0; attempt < 45; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2000));
    const response = await fetch(`/api/investigations/${repo}/jobs/${data.job_id}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Status HTTP ${response.status}`);
    const status = await response.json();
    if (["completed", "cancelled", "failed"].includes(status.status)) {
      console.log("Terminal mock orchestration:", { job_id: status.job_id, status: status.status,
        attempts: status.attempts, error_code: status.error_code, operation: status.operation });
      return;
    }
  }
  console.log("No terminal status within 90 seconds; check dispatcher and worker logs.");
})().catch(error => console.error("Verification failed:", error.message));
