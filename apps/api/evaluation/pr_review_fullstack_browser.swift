import AppKit
import Foundation
import WebKit
final class Test: NSObject, WKNavigationDelegate {
 let port = ProcessInfo.processInfo.environment["RP_WEB_PORT"]!
 let cookiePath = ProcessInfo.processInfo.environment["RP_COOKIES"]!
 var view: WKWebView?; var window: NSWindow?; var stage = 0; var done = false
 func start() {
  NSApplication.shared.setActivationPolicy(.regular)
  let conf = WKWebViewConfiguration(); conf.websiteDataStore = .nonPersistent()
  let width = CGFloat(Int(ProcessInfo.processInfo.environment["RP_WIDTH"] ?? "1440")!), height = CGFloat(Int(ProcessInfo.processInfo.environment["RP_HEIGHT"] ?? "900")!)
  let win=NSWindow(contentRect:NSRect(x:0,y:0,width:width,height:height),styleMask:[.titled,.closable],backing:.buffered,defer:false)
  let web=WKWebView(frame:NSRect(x:0,y:0,width:width,height:height),configuration:conf)
  win.contentView=web;win.makeKeyAndOrderFront(nil);window=win;view=web;web.navigationDelegate=self
  do {
   let data=try Data(contentsOf:URL(fileURLWithPath:cookiePath)); let cookies=try JSONDecoder().decode([String:String].self,from:data)
   let group=DispatchGroup()
   for (name,value) in cookies {
    guard let cookie=HTTPCookie(properties:[.name:name,.value:value,.domain:"127.0.0.1",.path:"/",.secure:"FALSE"]) else {fatalError("cookie")}
    group.enter();conf.websiteDataStore.httpCookieStore.setCookie(cookie){group.leave()}
   }
   group.notify(queue:.main){web.load(URLRequest(url:URL(string:"http://127.0.0.1:\(self.port)/")!))}
  } catch {print("BROWSER_SETUP_FAILED");exit(1)}
 }
 func webView(_ webView: WKWebView,didFinish navigation: WKNavigation!) {
  let js = #"""
  const wait = async (fn, label) => { for(let i=0;i<120;i++){let v=fn(); if(v)return v; await new Promise(r=>setTimeout(r,100));} throw Error('timeout: '+label); };
  const body=()=>document.body.innerText;
  const button=(x)=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===x);
  if (stage===0) {
   if(innerWidth!==width||innerHeight!==height) throw Error(`viewport ${innerWidth}x${innerHeight}`);
   const field=await wait(()=>document.querySelector('#pr-review-url'),'PR form');
   const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
   setter.call(field,mode==='httpx'?'https://github.com/encode/httpx/pull/3690':'https://github.com/alice/public/pull/7'); field.dispatchEvent(new Event('input',{bubbles:true}));
   await wait(()=>button('Review pull request'),'submit'); button('Review pull request').click();
   if(mode==='httpx'){ await wait(()=>body().includes('src/ahttpx/_parsers.py'),'HTTPX files'); if(!['src/ahttpx/_parsers.py','src/ahttpx/_server.py','src/httpx/_parsers.py','src/httpx/_server.py','20380490fd0bd13c68704080754c1385bff96d69','350221558d4f079fc4ab3673d81a4bc730fbb9c3','partial','Findings (0)'].every(x=>body().includes(x))) throw Error('HTTPX review mismatch'); const d=document.querySelector('section[aria-label=\"Pull request reviews\"] details summary'); if(!d)throw Error('diff not available');d.click(); if(!document.querySelector('section[aria-label=\"Pull request reviews\"] pre code'))throw Error('diff not rendered'); return 'HTTPX offline review displayed'; }
   await wait(()=>body().includes(tsmode ? 'TS-EVAL-001' : 'PY-SHELL-001'),'finding');
   if(!body().includes('Recorded files checked by enabled rules: 1') || !body().includes('Recorded files not fully checked: 0')) throw Error('coverage counts missing');
   if(fork && !body().includes('Head repository: contributor/public')) throw Error('fork identity missing');
   if(!body().includes('Source SHA-256 ' + (tsmode ? 'd19487a670bcabc8c5623b4f4a0015dc9582ef406a63e71efcdb8d287d60e8a4' : 'fae2d474ca2c90cf752fe728dddbd462d928400c2b16490454facc37601830f7'))) throw Error('finding identity missing');
   await wait(()=>button('useful'),'feedback button'); button('useful').click();
   await wait(()=>body().includes('Feedback: useful'),'feedback saved');
   return 'submitted and feedback persisted';
  }
  const entry=await wait(()=>[...document.querySelectorAll('button')].find(b=>b.textContent.includes(mode==='httpx'?'wait_ready':'Synthetic PR')),'review history');entry.click();
  if(mode==='httpx'){await wait(()=>body().includes('src/ahttpx/_parsers.py'),'HTTPX after reload');return 'HTTPX offline review after reload';}
  await wait(()=>body().includes('Feedback: useful'),'feedback after reload');
  if(!body().includes(tsmode ? 'TS-EVAL-001' : 'PY-SHELL-001') || !body().includes('partial')) throw Error('finding or coverage missing');
  return 'refresh and reopen persisted';
  """#
  webView.callAsyncJavaScript(js,arguments:["stage":stage,"mode":ProcessInfo.processInfo.environment["RP_MODE"] ?? "synthetic","fork":ProcessInfo.processInfo.environment["PR_FORK_TEST"] == "1","tsmode":ProcessInfo.processInfo.environment["PR_TS_TEST"] == "1","width":Int(ProcessInfo.processInfo.environment["RP_WIDTH"] ?? "1440")!,"height":Int(ProcessInfo.processInfo.environment["RP_HEIGHT"] ?? "900")!],in:nil,in:.page){ result in
   switch result {
    case .success(let value):
     print("BROWSER_STAGE \(self.stage): \(value ?? "ok")")
     if self.stage==0 {self.stage=1;webView.reload()} else if let marker=ProcessInfo.processInfo.environment["RP_REVOCATION_MARKER"], !marker.isEmpty {
      do { try Data("synthetic revocation".utf8).write(to:URL(fileURLWithPath:marker)) }
      catch { print("BROWSER_REVOCATION_SETUP_FAILED");exit(1) }
      let denial = #"""
       const section=()=>document.querySelector('section[aria-label="Pull request reviews"]');
       for(let i=0;i<200;i++){const text=section()?.innerText??'';if(text.includes('Reviews could not be loaded') && !text.includes('TS-EVAL-001') && !text.includes('Source SHA-256')) return 'revocation cleared cached review';await new Promise(r=>setTimeout(r,100));}
       throw Error('revocation did not clear cached review');
      """#
      webView.callAsyncJavaScript(denial,arguments:[:],in:nil,in:.page){ result in
       switch result { case .success(let value):print("BROWSER_REVOCATION: \(value ?? "ok")");self.done=true;NSApplication.shared.terminate(nil)
       case .failure(let error):print("BROWSER_REVOCATION_FAILED \(error.localizedDescription)");exit(1) }
      }
     } else {self.done=true;NSApplication.shared.terminate(nil)}
    case .failure(let error): print("BROWSER_FAILURE \((error as NSError).userInfo["WKJavaScriptExceptionMessage"] ?? error.localizedDescription)");exit(1)
   }
  }
 }
 func webView(_ webView:WKWebView,didFail navigation:WKNavigation!,withError error:Error){print("BROWSER_LOAD_FAILED \(error.localizedDescription)");exit(1)}
}
let t=Test();DispatchQueue.main.async{t.start()};DispatchQueue.main.asyncAfter(deadline:.now()+70){if !t.done {print("BROWSER_TIMEOUT");exit(1)}};NSApplication.shared.run()
