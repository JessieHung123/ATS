"""在獨立 Chrome／Edge 設定檔實測既有 API。會呼叫 Gemini，僅使用虛構測試職缺。"""
import json
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect


def run():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    profile = tempfile.mkdtemp(prefix="ats-autofill-")
    edge = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not edge.exists():
        edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    process = subprocess.Popen([str(edge), "--headless=new", "--disable-gpu", "--no-first-run",
                                f"--remote-debugging-port={port}", f"--user-data-dir={profile}", "about:blank"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=1))
                target = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(.2)
        else:
            raise RuntimeError("瀏覽器偵錯介面未啟動")
        with connect(target["webSocketDebuggerUrl"], max_size=2**23) as ws:
            counter = 0

            def command(method, params):
                nonlocal counter
                counter += 1
                ws.send(json.dumps({"id": counter, "method": method, "params": params}))
                while True:
                    result = json.loads(ws.recv(timeout=240))
                    if result.get("id") == counter:
                        if "error" in result:
                            raise RuntimeError(result["error"])
                        return result.get("result", {})

            command("Page.enable", {})
            command("Page.navigate", {"url": "http://127.0.0.1:8765/"})
            time.sleep(2)
            script = r"""(async () => {
              const assert=(v,m)=>{if(!v)throw Error(m)};
              const wait=async(fn)=>{for(let i=0;i<2200;i++){if(fn())return;await new Promise(r=>setTimeout(r,100))}throw Error('UI timeout')};
              const input=(sel,v)=>{const e=document.querySelector(sel);e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}))};
              await wait(()=>samples.jobs.length && document.querySelector('#model-select').value);
              const originalFetch=window.fetch;
              const requests=[];
              window.fetch=async(...args)=>{const response=await originalFetch(...args);if(args[0]==='/api/job/autofill')requests.push({path:args[0],status:response.status,body:await response.clone().json()});return response};
              const reports=[];
              const fields=['years','education','required','bonus'];
              const reset=(title)=>{for(const key of fields)input('#f-'+key,'');input('#f-jd','');input('#f-title',title)};
              const generate=async()=>{const b=document.querySelector('#btn-job-autofill');b.click();assert(b.disabled && b.textContent.includes('填寫中'),'loading missing');await wait(()=>!b.disabled);assert(!document.querySelector('#job-msg').textContent.includes('⚠'),document.querySelector('#job-msg').textContent)};
              for(const title of ['人力資源主管','行銷企劃專員']) {
                reset(title);
                await generate();
                assert(fields.every(k=>document.querySelector('#f-'+k).value.trim()),'empty form field');
                assert(document.querySelector('#f-jd').value.trim(),'empty JD');
                assert(fields.every(k=>document.querySelector('#f-'+k).value===state.fields[k]),'DOM/state mismatch');
                assert(document.querySelector('#autofill-notice').textContent.includes('一般性建議'),'missing title notice');
                const response=requests.at(-1);
                assert(response.status===200 && response.body.source==='ai','not real AI result');
                reports.push({title,model:response.body.model,http:response.status,filled:Object.fromEntries(fields.map(k=>[k,document.querySelector('#f-'+k).value.length])),jd:state.jd.length});
              }
              // 真實 JD 與手動欄位保留，同時驗證畫面自動填入但沒有 input 事件的情境。
              reset('人力資源主管');
              const manual='HR 已確認：至少 5 年相關經驗';
              const jd='負責招募流程與員工訓練，須熟悉台灣勞動法令。';
              document.querySelector('#f-years').value=manual;
              document.querySelector('#f-jd').value=jd;
              await generate();
              assert(state.fields.years===manual && document.querySelector('#f-years').value===manual,'manual years overwritten');
              assert(state.jd===jd && document.querySelector('#f-jd').value===jd,'JD overwritten');
              assert(requests.at(-1).body.basis==='jd','JD basis missing');
              input('#f-bonus','');assert(state.fields.bonus==='','cannot delete draft text');
              input('#f-bonus','人資手動補充');assert(state.fields.bonus==='人資手動補充','cannot edit draft text');
              document.querySelector('#btn-confirm-job').click();
              const extract=document.querySelector('#btn-extract');extract.click();await wait(()=>!extract.disabled);
              assert(state.matrix?.competencies.length,'matrix failed');
              assert(state.matrixSource==='ai','matrix silently fell back: '+document.querySelector('#extract-msg').textContent);
              const matrixCount=state.matrix.competencies.length;
              // 注入可控錯誤，檢查錯誤顯示與原始內容保留；不增加 Gemini 呼叫。
              input('#f-education','');
              const before=jobSignature();
              window.fetch=async(path,...args)=>path==='/api/job/autofill'?new Response(JSON.stringify({detail:'Gemini 測試錯誤（429）'}),{status:502,headers:{'Content-Type':'application/json'}}):originalFetch(path,...args);
              const b=document.querySelector('#btn-job-autofill');b.click();await wait(()=>!b.disabled);
              assert(document.querySelector('#job-msg').textContent.includes('429'),'error hidden');assert(jobSignature()===before,'failure changed fields');
              window.fetch=async(path,...args)=>path==='/api/job/autofill'?new Response(JSON.stringify({source:'ai',fields:{years:'bad'}}),{status:200,headers:{'Content-Type':'application/json'}}):originalFetch(path,...args);
              b.click();await wait(()=>!b.disabled);assert(document.querySelector('#job-msg').textContent.includes('格式不完整'),'malformed response hidden');assert(jobSignature()===before,'partial malformed write');
              window.fetch=originalFetch;
              return {passed:true,reports,manualAndJdPreserved:true,editableAndDeletable:true,matrixCount,matrixSource:state.matrixSource,errorVisible:true,malformedResponseAtomic:true};
            })()"""
            result = command("Runtime.evaluate", {"expression": script, "awaitPromise": True, "returnByValue": True})
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            print(json.dumps(result["result"].get("value"), ensure_ascii=True))
    finally:
        process.terminate()
        process.wait(timeout=20)


if __name__ == "__main__":
    run()
