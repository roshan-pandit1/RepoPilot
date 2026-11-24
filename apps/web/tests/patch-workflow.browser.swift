// Synthetic WebKit workflow test. Point only at the disposable, loopback-only
// frontend preview documented in patch-workflow-verification.md.
import AppKit
import Foundation
import WebKit

final class PatchWorkflowCheck: NSObject, WKNavigationDelegate {
    let modes = ["review", "unavailable", "unauthorized"]
    var index = 0
    var window: NSWindow?
    var view: WKWebView?
    var finished = false

    func start() {
        NSApplication.shared.setActivationPolicy(.regular)
        next()
    }

    func next() {
        if index == modes.count {
            finished = true
            print("BROWSER_RESULT: 3 passed, 0 failed, 0 skipped")
            NSApplication.shared.terminate(nil)
            return
        }
        let mode = modes[index]
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        let bootstrap = #"""
        (() => {
          const mode = '__MODE__';
          const repo = '902', issue = '990', job = '11111111-1111-4111-8111-111111111111';
          const snapshot = '22222222-2222-4222-8222-222222222222';
          const chunk = '33333333-3333-4333-8333-333333333333';
          const proposal = '44444444-4444-4444-8444-444444444444';
          const evidenceId = '55555555-5555-4555-8555-555555555555';
          const commit = 'a'.repeat(40), date = '2026-01-01T00:00:00Z';
          const root = `/api/investigations/${repo}/jobs/${job}`;
          const patches = `${root}/patch-proposals`;
          const calls = [];
          const state = { created: false, status: 'queued', review: 'unreviewed', test: 'VALIDATION_UNAVAILABLE' };
          const json = (data, status = 200) => new Response(JSON.stringify(data), {
            status, headers: { 'content-type': 'application/json' }
          });
          const summary = () => ({ id: proposal, status: state.status, snapshot_id: snapshot,
            commit_sha: commit, review_state: state.review, error_code: null,
            dispatch_status: state.status === 'queued' ? 'pending' : 'processed' });
          const detail = () => state.status === 'queued' ? summary() : ({ ...summary(),
            diff: '--- a/src/add.py\n+++ b/src/add.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n',
            rationale: 'Synthetic change for review.', provider: 'synthetic-test', model: 'fixture-v1',
            changed_files: [{ path: 'src/add.py' }],
            evidence: [{ id: evidenceId, path: 'src/add.py', start_line: 1, end_line: 2 }],
            static_result: { status: 'passed' },
            test_result: { status: state.test, sandbox_used: false, test_executed: false, tests_run: [] }
          });
          window.__p5 = {
            calls, setGenerated: () => { state.status = 'static_validated'; },
            finishValidation: () => { state.status = 'static_validated'; state.test = 'VALIDATION_UNAVAILABLE'; }
          };
          window.fetch = async (input, options = {}) => {
            const url = new URL(typeof input === 'string' ? input : input.url, location.origin);
            const method = (options.method || 'GET').toUpperCase();
            calls.push({ path: url.pathname, method });
            if (url.origin !== location.origin) return json({ detail: 'blocked' }, 403);
            if (url.pathname === '/api/health') return json({ ready: true });
            if (url.pathname === '/api/auth/me') return json({ user: { login: 'synthetic-user' }, demo: false });
            if (url.pathname === '/api/dashboard' && !url.search) return json([{ id: repo, full_name: 'sample/repository', enabled: true }]);
            if (url.pathname === '/api/dashboard') return json({ items: [], ingestion: { pending: 0, processed: 0, ignored: 0, failed: 0 } });
            if (url.pathname === `/api/investigations/${repo}/history`) return json({ items: [{
              job_id: job, issue_number: 5, issue_title: 'Synthetic addition issue', status: 'completed',
              created_at: date, updated_at: date, attempts: 1, evidence_count: 1,
              report_status: null, operation: 'code_evidence'
            }], next_offset: null });
            if (url.pathname === `/api/repositories/${repo}/issues/5/context`) return json({
              repository_id: repo, issue_id: issue, number: 5, title: 'Synthetic addition issue',
              body: 'The synthetic addition result is incorrect.', state: 'open', labels: [], comments: [],
              created_at: date, updated_at: date, retrieved_at: date,
              url: 'https://github.com/sample/repository/issues/5',
              truncation: { title: false, body: false, labels: false, comments: false, total: false }
            });
            if (url.pathname === root) return json({ job_id: job, issue_id: issue, issue_number: 5,
              status: 'completed', attempts: 1, operation: 'code_evidence', snapshot_id: snapshot,
              commit_sha: commit, retrieval_status: 'completed', evidence_count: 1, error_code: null, snapshot_partial: false });
            if (url.pathname === `${root}/evidence`) return json({ job_id: job, snapshot_id: snapshot,
              commit_sha: commit, retrieval_status: 'completed', evidence_count: 1, items: [{
                chunk_id: chunk, rank: 1, query_id: 'symbol', query_rank: 1, method: 'keyword',
                path: 'src/add.py', symbol: 'add', start_line: 1, end_line: 2, commit_sha: commit,
                url: `https://github.com/sample/repository/blob/${commit}/src/add.py#L1-L2`,
                snippet: 'def add(a, b):\n    return a - b\n', snippet_truncated: false, snippet_unavailable: false
              }] });
            if (url.pathname === `${root}/report` || url.pathname === `${root}/code-intelligence`) return json({}, 404);
            if (url.pathname === patches && method === 'GET') return json({
              available: mode !== 'unavailable', reason: mode === 'unavailable' ? 'Patch generation provider is unavailable.' : null,
              items: state.created ? [summary()] : [] });
            if (url.pathname === patches && method === 'POST') {
              if (mode === 'unauthorized') return json({ detail: 'Not authorized' }, 401);
              const inputBody = JSON.parse(options.body);
              if (!/^[0-9a-f-]{36}$/i.test(inputBody.request_id)) return json({}, 422);
              await new Promise(resolve => setTimeout(resolve, 400));
              state.created = true;
              return json(summary(), 202);
            }
            if (url.pathname === `${patches}/${proposal}` && method === 'GET') return json(detail());
            if (url.pathname === `${patches}/${proposal}/static-validation` && method === 'POST') return json({ status: 'passed' });
            if (url.pathname === `${patches}/${proposal}/test-validation` && method === 'POST') {
              state.status = 'validation_pending'; state.test = 'pending'; return json(summary(), 202);
            }
            if (url.pathname === `${patches}/${proposal}/review` && method === 'POST') {
              const inputBody = JSON.parse(options.body);
              if (inputBody.decision !== 'approved_for_review') return json({}, 422);
              state.review = inputBody.decision; return json(summary());
            }
            if (url.pathname.endsWith('/index-status')) return json({ status: 'not_indexed', commit_sha: null,
              indexed_at: null, file_count: 0, chunk_count: 0, skipped_count: 0, error_code: null });
            if (url.pathname.endsWith('/embedding-status')) return json({ status: 'not_started', ready: false,
              generation_available: false, completed_chunks: 0, total_chunks: 0, provider: null, model: null,
              dimensions: null, job_commit: null, error_code: null });
            return json({ detail: 'Synthetic endpoint unavailable' }, 404);
          };
        })();
        """#.replacingOccurrences(of: "__MODE__", with: mode)
        config.userContentController.addUserScript(WKUserScript(source: bootstrap, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        let web = WKWebView(frame: NSRect(x: 0, y: 0, width: 1280, height: 900), configuration: config)
        let win = NSWindow(contentRect: NSRect(x: 20, y: 20, width: 1280, height: 900), styleMask: [.titled, .closable], backing: .buffered, defer: false)
        win.contentView = web
        win.makeKeyAndOrderFront(nil)
        NSApplication.shared.activate(ignoringOtherApps: true)
        window = win
        view = web
        web.navigationDelegate = self
        web.load(URLRequest(url: URL(string: "http://127.0.0.1:3159/")!))
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let script = #"""
        const waitFor = async (predicate, label) => {
          for (let i = 0; i < 200; i++) {
            const value = predicate(); if (value) return value;
            await new Promise(resolve => setTimeout(resolve, 50));
          }
          throw new Error('Timed out: ' + label);
        };
        const bodyText = () => document.body.innerText;
        const button = text => [...document.querySelectorAll('button')].find(item => item.textContent.trim() === text);
        const check = (value, label) => { if (!value) throw new Error(label); };
        const open = await waitFor(() => [...document.querySelectorAll('button')].find(item =>
          item.getAttribute('aria-label')?.startsWith('Open investigation for issue 5')), 'investigation history');
        open.click();
        await waitFor(() => bodyText().includes('Retrieved code evidence'), 'evidence');
        await waitFor(() => bodyText().includes('Proposed fixes'), 'patch panel');
        const generate = await waitFor(() => button('Generate proposed fix'), 'generate button');
        if (mode === 'unavailable') {
          await waitFor(() => bodyText().includes('Patch generation provider is unavailable.'), 'provider unavailable');
          check(generate.disabled, 'Unavailable provider must disable generation');
          check(!window.__p5.calls.some(call => call.method === 'POST'), 'Unexpected mutation');
          return 'provider unavailable';
        }
        await waitFor(() => !generate.disabled, 'provider availability');
        generate.click();
        if (mode === 'unauthorized') {
          await waitFor(() => bodyText().includes('The request could not be completed.'), 'authorization error');
          check(!bodyText().includes('Statically validated proposal'), 'Unauthorized result displayed');
          return 'authorization error';
        }
        await waitFor(() => window.__p5.calls.some(call => call.path.endsWith('/patch-proposals') && call.method === 'POST'), 'generation request');
        await waitFor(() => generate.disabled, 'generation busy state');
        await waitFor(() => bodyText().includes('Proposal: queued'), 'queued proposal');
        check(!bodyText().includes('Statically validated proposal'), 'Queued job incorrectly validated');
        window.__p5.setGenerated();
        button('Refresh proposal').click();
        await waitFor(() => bodyText().includes('Statically validated proposal'), 'generated proposal');
        check(bodyText().includes('src/add.py') && bodyText().includes('src/add.py:1–2'), 'Evidence or file missing');
        check(document.querySelector('section[aria-label="Proposed fixes"] pre code')?.textContent.includes('return a + b'), 'Diff missing');
        button('Recheck static validation').click();
        await waitFor(() => window.__p5.calls.some(call => call.path.endsWith('/static-validation') && call.method === 'POST'), 'static validation');
        await waitFor(() => button('Request isolated tests') && !button('Request isolated tests').disabled, 'test action');
        button('Request isolated tests').click();
        await waitFor(() => bodyText().includes('Proposal: validation_pending'), 'pending validation');
        window.__p5.finishValidation();
        button('Refresh proposal').click();
        await waitFor(() => bodyText().includes('Automated tests were not run. This is a proposed patch, not a verified fix.'), 'unavailable test result');
        check(!bodyText().includes('Sandbox used: yes') && !bodyText().includes('Baseline:'), 'False execution success');
        await waitFor(() => button('Approve for review') && !button('Approve for review').disabled, 'review action');
        button('Approve for review').click();
        await waitFor(() => bodyText().includes('Review: approved for review'), 'review recorded');
        check(bodyText().includes('does not apply this patch or publish a pull request'), 'Review warning missing');
        const writes = window.__p5.calls.filter(call => call.method !== 'GET');
        check(writes.length === 4 && writes.every(call => call.method === 'POST' && call.path.includes('/patch-proposals')),
              'Unexpected request or repository write');
        return 'synthetic proposal reviewed; tests unavailable';
        """#
        webView.callAsyncJavaScript(script, arguments: ["mode": modes[index]], in: nil, in: .page) { result in
            switch result {
            case .success(let value):
                print("BROWSER_PASS \(self.modes[self.index]): \(value ?? "no detail")")
                self.window?.orderOut(nil)
                self.index += 1
                self.next()
            case .failure(let error):
                let detail = (error as NSError).userInfo["WKJavaScriptExceptionMessage"] ?? error.localizedDescription
                print("BROWSER_FAIL \(self.modes[self.index]): \(detail)")
                webView.evaluateJavaScript("JSON.stringify({visibility:document.visibilityState,calls:window.__p5?.calls,body:document.body.innerText.slice(-1800)})") { diagnostic, _ in
                    print("BROWSER_DIAGNOSTIC: \(diagnostic ?? "unavailable")")
                    exit(1)
                }
            }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        print("BROWSER_LOAD_FAIL: \(error.localizedDescription)")
        exit(1)
    }
}

let check = PatchWorkflowCheck()
DispatchQueue.main.async { check.start() }
DispatchQueue.main.asyncAfter(deadline: .now() + 90) {
    if !check.finished { print("BROWSER_TIMEOUT"); exit(1) }
}
NSApplication.shared.run()
