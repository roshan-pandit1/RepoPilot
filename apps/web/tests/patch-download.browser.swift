// Synthetic WebKit native download regression. Start an isolated Next.js preview
// on 127.0.0.1:3817 first; every application API response below is a fixture.
// This does not touch the system clipboard or verify the live API authorization path.
import AppKit
import Foundation
import WebKit
import CryptoKit

let privateDirectory = URL(fileURLWithPath: "/private/tmp", isDirectory: true)
    .appendingPathComponent("repopilot-p181-download-" + UUID().uuidString, isDirectory: true)


var ownsPrivateDirectory = false
func fail() -> Never {
 if ownsPrivateDirectory {
  do {
   try FileManager.default.removeItem(at: privateDirectory)
   guard !FileManager.default.fileExists(atPath: privateDirectory.path) else {
    print("P181_FAILURE_CLEANUP_FAIL"); fflush(stdout); exit(2)
   }
   print("P181_FAILURE_CLEANUP_OK")
  } catch { print("P181_FAILURE_CLEANUP_FAIL: \(error)"); fflush(stdout); exit(2) }
 }
 fflush(stdout); exit(1)
}

final class Check: NSObject, WKNavigationDelegate, WKDownloadDelegate {
 let fixture = "--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n"
 let expectedHash = "8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7"
 let directory = privateDirectory
 var dest: URL?; var view: WKWebView!; var window: NSWindow!; var done = false
 func start() {
  do {
   try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false, attributes: [.posixPermissions: 0o700])
   ownsPrivateDirectory = true
  } catch { print("P181_PRIVATE_DIRECTORY_FAIL"); fail() }
  NSApplication.shared.setActivationPolicy(.regular)
  let config = WKWebViewConfiguration(); config.websiteDataStore = .nonPersistent()
  let bootstrap = #"""

        (() => {
          const mode = 'review';
          const repo = '902', issue = '990', job = '11111111-1111-4111-8111-111111111111';
          const snapshot = '22222222-2222-4222-8222-222222222222';
          const chunk = '33333333-3333-4333-8333-333333333333';
          const proposal = '44444444-4444-4444-8444-444444444444';
          const evidenceId = '55555555-5555-4555-8555-555555555555';
          const commit = 'a'.repeat(40), date = '2026-01-01T00:00:00Z';
          const root = `/api/investigations/${repo}/jobs/${job}`;
          const patches = `${root}/patch-proposals`;
          const calls = [];
          const state = { created: true, status: 'static_validated', review: 'unreviewed', test: 'VALIDATION_UNAVAILABLE' };
          const json = (data, status = 200) => new Response(JSON.stringify(data), {
            status, headers: { 'content-type': 'application/json' }
          });
          const summary = () => ({ id: proposal, status: state.status, snapshot_id: snapshot,
            commit_sha: commit, review_state: state.review, error_code: null,
            dispatch_status: state.status === 'queued' ? 'pending' : 'processed' });
          const detail = () => state.status === 'queued' ? summary() : ({ ...summary(),
            diff: '--- a/src/arithmetic.py\n+++ b/src/arithmetic.py\n@@ -1,2 +1,2 @@\n def add(a: int, b: int) -> int:\n-    return a - b\n+    return a + b\n',
            patch_sha256: '8d74d6e35955c7e3c7068fc709b09b4d59b2b4efcd6f17076d9b032e159150e7', export_available: true, source_stale: false, export_reason: null,
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
            if (url.pathname === `${patches}/${proposal}/export` && method === 'GET') {
              if (url.searchParams.get('sha256') !== detail().patch_sha256) return json({}, 409);
              return new Response(detail().diff, { headers: { 'Content-Type': 'text/x-diff', 'X-Patch-SHA256': detail().patch_sha256, 'X-Source-Commit': commit, 'X-Source-Snapshot': snapshot } });
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

"""#
  config.userContentController.addUserScript(WKUserScript(source: bootstrap, injectionTime: .atDocumentStart, forMainFrameOnly: true))
  view = WKWebView(frame: NSRect(x:0,y:0,width:1280,height:900), configuration:config)
  window = NSWindow(contentRect:NSRect(x:20,y:20,width:1280,height:900),styleMask:[.titled,.closable],backing:.buffered,defer:false)
  window.contentView=view; window.makeKeyAndOrderFront(nil); NSApplication.shared.activate(ignoringOtherApps:true)
  view.navigationDelegate=self; view.load(URLRequest(url:URL(string:"http://127.0.0.1:3817/")!))
 }
 func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
  let code = #"""
   const wait=async(f,l)=>{for(let i=0;i<300;i++){let x=f();if(x)return x;await new Promise(r=>setTimeout(r,50));}throw Error(l)};
   const open=await wait(()=>[...document.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')?.startsWith('Open investigation for issue 5')),'open investigation'); open.click();
   await wait(()=>document.body.innerText.includes('Proposed fixes'),'proposal panel');
   const item=await wait(()=>[...document.querySelectorAll('button')].find(b=>b.textContent.includes('44444444-4444-4444-8444-444444444444')),'proposal'); item.click();
   const button=await wait(()=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()==='Download candidate .patch' && !b.disabled),'download action');
   button.scrollIntoView({block:'center',behavior:'instant'});
   button.addEventListener('click',e=>{window.__nativeTrusted=e.isTrusted}, {capture:true});
   const r=button.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
  """#
  webView.callAsyncJavaScript(code,arguments:[:],in:nil,in:.page) { result in
   switch result {
   case .failure(let e): print("P181_UI_FAIL \(e)"); fail()
   case .success(let any):
    guard let r=any as? [String:Double], let x=r["x"],let y=r["y"] else { print("P181_COORD_FAIL");fail() }
    let p=NSPoint(x:x,y:self.view.bounds.height-y)
    guard let down=NSEvent.mouseEvent(with:.leftMouseDown,location:p,modifierFlags:[],timestamp:ProcessInfo.processInfo.systemUptime,windowNumber:self.window.windowNumber,context:nil,eventNumber:1,clickCount:1,pressure:1),let up=NSEvent.mouseEvent(with:.leftMouseUp,location:p,modifierFlags:[],timestamp:ProcessInfo.processInfo.systemUptime+0.02,windowNumber:self.window.windowNumber,context:nil,eventNumber:2,clickCount:1,pressure:0) else { fail() }
    NSApplication.shared.postEvent(down,atStart:false); NSApplication.shared.postEvent(up,atStart:false)
   }
  }
 }
 func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping (WKNavigationActionPolicy)->Void) { decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow) }
 func webView(_ webView:WKWebView,navigationAction:WKNavigationAction,didBecome download:WKDownload) { download.delegate=self }
 func webView(_ webView:WKWebView,navigationResponse:WKNavigationResponse,didBecome download:WKDownload) { download.delegate=self }
 func download(_ download:WKDownload,decideDestinationUsing response:URLResponse,suggestedFilename:String,completionHandler:@escaping (URL?)->Void) {
   guard suggestedFilename == "repopilot-44444444-4444-4444-8444-444444444444.patch" else {print("P181_BAD_FILENAME");completionHandler(nil);fail()}
   dest=directory.appendingPathComponent(suggestedFilename); print("P181_DESTINATION_ACCEPTED"); completionHandler(dest)
 }
 func downloadDidFinish(_ download:WKDownload) {
   do { guard let dest=dest else {fail()}
     guard try FileManager.default.attributesOfItem(atPath: dest.path)[.type] as? FileAttributeType == .typeRegular else { print("P181_NOT_REGULAR_FILE");fail() }
     let data=try Data(contentsOf:dest); let expected=Data(fixture.utf8)
     let hash=SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined()
     guard data.count==133, data==expected, hash==expectedHash else {print("P181_BYTES_FAIL count=\(data.count) sha=\(hash)");fail()}
     view.evaluateJavaScript("window.__nativeTrusted === true") { value,error in
       guard error == nil, value as? Bool == true else {print("P181_NOT_TRUSTED_NATIVE_EVENT");fail()}
       do { try FileManager.default.removeItem(at: self.directory) } catch { print("P181_CLEANUP_FAIL");fail() }
       guard !FileManager.default.fileExists(atPath:self.directory.path) else { print("P181_CLEANUP_FAIL");fail() }
       print("P181_NATIVE_DOWNLOAD_PASS bytes=133 sha256=\(hash) trusted_click=true exact_bytes=true safe_filename=true cleanup=true")
       self.done=true; NSApplication.shared.terminate(nil)
     }
   } catch {print("P181_READ_FAIL \(error)");fail()}
 }
 func download(_ download:WKDownload,didFailWithError error:Error,resumeData:Data?) {print("P181_DOWNLOAD_FAIL \(error)");fail()}
 func webView(_ webView:WKWebView,didFail navigation:WKNavigation!,withError error:Error) { print("P181_NAV_FAIL \(error)");fail() }
}
let check=Check(); DispatchQueue.main.async {check.start()}; DispatchQueue.main.asyncAfter(deadline:.now()+75) { if !check.done {print("P181_TIMEOUT");fail()} }; NSApplication.shared.run()
