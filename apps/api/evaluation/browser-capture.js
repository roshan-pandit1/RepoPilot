// Paste into the signed-in localhost:3000 browser console; never prints or exports cookies or source.
(async () => {
  if (location.origin !== "http://localhost:3000") throw new Error("Open the signed-in localhost:3000 dashboard first.");
  const queries = [{"id": "sync", "question": "Where is repository issue synchronization handled?"}, {"id": "signature", "question": "How are webhook signatures verified?"}, {"id": "webhook", "question": "Where are webhook request bodies and signatures checked?"}, {"id": "dispatch", "question": "Where are queued issue and synchronization jobs dispatched?"}, {"id": "authorization", "question": "How is current repository access enforced?"}, {"id": "tenant", "question": "Where are enabled repositories scoped to a tenant?"}, {"id": "csrf", "question": "How are state-changing requests protected against CSRF?"}, {"id": "principal", "question": "How is an authenticated session resolved?"}, {"id": "login", "question": "Where does GitHub OAuth login begin with PKCE?"}, {"id": "callback", "question": "Where is the GitHub OAuth callback verified?"}, {"id": "logout", "question": "How is a user session revoked when signing out?"}, {"id": "enroll", "question": "How is a personal GitHub installation enrolled?"}, {"id": "choose", "question": "Where is a public repository selected for an installation?"}, {"id": "installations", "question": "Where are personal GitHub installations verified?"}, {"id": "visible", "question": "How does the app check visible GitHub repositories?"}, {"id": "accept", "question": "Where are webhook delivery and outbox records written?"}, {"id": "process", "question": "Where are queued webhook issue events applied?"}, {"id": "revoke", "question": "Where are installation and repository revocations handled?"}, {"id": "health", "question": "How does the application check database and Redis readiness?"}, {"id": "delivery", "question": "Where are duplicate webhook deliveries represented?"}];
  const repo = "1435878031";
  const commit = "63491908290e6874dbaaf2b15c2a96473aad1324";
  const csrfCookie = document.cookie.split("; ").find(v => v.startsWith("rp_csrf="));
  if (!csrfCookie) throw new Error("Sign in again before running the benchmark.");
  const csrf = decodeURIComponent(csrfCookie.slice("rp_csrf=".length));
  const statusResponse = await fetch(`/api/code/${repo}/embedding-status`, {cache: "no-store"});
  if (!statusResponse.ok) throw new Error(`Embedding status failed: HTTP ${statusResponse.status}`);
  const state = await statusResponse.json();
  if (state.snapshot_commit !== commit || (state.provider && state.provider !== "fake")) throw new Error("Snapshot or provider does not match the benchmark.");
  const capture = {repository: "roshan-pandit1/RepoPilot", repository_id: repo, commit_sha: commit, provider: state.provider, model: state.model, dimensions: state.dimensions, ready: state.ready, queries: []};
  for (const mode of ["keyword", "semantic", "hybrid"]) {
    for (const query of queries) {
      const start = performance.now();
      const response = await fetch(`/api/code/${repo}/search`, {method: "POST", cache: "no-store", headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf}, body: JSON.stringify({query: query.question, mode, limit: 10})});
      const latency = performance.now() - start;
      if (!response.ok) throw new Error(`Search failed: HTTP ${response.status}; ${mode} ${query.id}`);
      const data = await response.json();
      if (data.commit_sha !== commit) throw new Error("Snapshot changed during evaluation.");
      capture.queries.push({mode, id: query.id, latency_ms: latency, response: {commit_sha: data.commit_sha, mode: data.mode, fallback_reason: data.fallback_reason, items: data.items.map(({path, symbol, start_line, end_line, commit_sha, url}) => ({path, symbol, start_line, end_line, commit_sha, url}))}});
    }
  }
  const link = document.createElement("a");
  const objectUrl = URL.createObjectURL(new Blob([JSON.stringify(capture, null, 2)], {type: "application/json"}));
  link.href = objectUrl; link.download = "repopilot-eval-capture.json"; link.click();
  setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  console.log("Benchmark capture complete. No session cookies or source snippets were saved.");
})().catch(error => console.error("Benchmark failed:", error.message));
