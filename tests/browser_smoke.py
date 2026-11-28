"""以本機 Edge headless 驗證原生 JS 流程；先在 8000 埠啟動 FastAPI。"""
import json
import os
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.sync.client import connect

edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
profile = tempfile.mkdtemp(prefix="ats-browser-test-")
process = subprocess.Popen([str(edge), "--headless=new", "--disable-gpu", "--no-first-run",
                            "--remote-debugging-port=9237", f"--user-data-dir={profile}", "about:blank"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for attempt in range(100):
        try:
            tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9237/json", timeout=1))
            target = next(t for t in tabs if t["type"] == "page")
            break
        except Exception:
            time.sleep(.2)
    else:
        raise RuntimeError("Edge 偵錯介面未啟動")
    with connect(target["webSocketDebuggerUrl"], max_size=2**23) as ws:
        counter = 0

        def command(method, params):
            global counter
            counter += 1
            ws.send(json.dumps({"id": counter, "method": method, "params": params}))
            while True:
                result = json.loads(ws.recv(timeout=30))
                if result.get("id") == counter:
                    if "error" in result:
                        raise RuntimeError(result["error"])
                    return result.get("result", {})

        command("Page.enable", {})
        command("Page.addScriptToEvaluateOnNewDocument", {"source": "window.testErrors=[]; window.addEventListener('error',e=>testErrors.push(e.message)); window.addEventListener('unhandledrejection',e=>testErrors.push(String(e.reason)));"})
        command("Page.navigate", {"url": os.environ.get("ATS_TEST_URL", "http://127.0.0.1:8000")})
        time.sleep(2)
        script = r"""(async () => {
          const assert = (value, message) => { if (!value) throw Error(message); };
          const wait = async (fn) => { for(let i=0;i<100;i++){if(fn())return; await new Promise(r=>setTimeout(r,100));} throw Error('UI timeout'); };
          const input = (el,value) => { el.value=value; el.dispatchEvent(new Event('input',{bubbles:true})); };
          await wait(()=>samples.jobs.length);
          assert(!document.querySelector('#api-key'),'不應在瀏覽器輸入金鑰');
          document.querySelector('#use-ai').checked=false;
          input(document.querySelector('#f-title'),'資料分析師');
          document.querySelector('#btn-job-suggest').click();
          await wait(()=>state.jobDraft);
          assert(state.jd==='', '草稿不能自動套用');
          assert(document.querySelector('#job-draft').textContent.includes('一般性建議'), '缺少一般建議標示');
          const old=state.jobDraft.draft.skills.length;
          document.querySelector('[data-draft-add="skills"]').click();
          assert(state.jobDraft.draft.skills.length===old+1,'新增失敗');
          input(document.querySelector(`[data-section="skills"][data-index="${old}"]`),'Excel');
          document.querySelector(`[data-draft-del="skills"][data-index="${old}"]`).click();
          assert(state.jobDraft.draft.skills.length===old,'刪除失敗');
          input(document.querySelector('[data-section="skills"]'),'SQL');
          document.querySelector('#apply-job-draft').click();
          assert(state.jd.includes('SQL'),'確認套用失敗');
          document.querySelector('#btn-extract').click();
          await wait(()=>state.matrix);
          assert(state.matrix.competencies.length>0,'無職能');
          assert(document.querySelector('#matrix-source').parentElement.textContent.includes('職能矩陣'),'職能矩陣標題遺失');
          assert(document.querySelector('#matrix-source').textContent,'職能矩陣來源標籤遺失');
          assert(!document.querySelector('#m1').textContent.includes('可以直接新增、刪除、改名職能'),'職能矩陣提示文字仍顯示');
          let select=document.querySelector('[data-field="category"]');
          select.value='knowledge'; select.dispatchEvent(new Event('change',{bubbles:true}));
          assert(state.matrix.competencies[0].category==='knowledge','類別變更失敗');
          const competencyCount=state.matrix.competencies.length;
          document.querySelector('[data-add="hard"]').click();
          const addedCompetency=state.matrix.competencies[state.matrix.competencies.length-1];
          input(document.querySelector(`[data-id="${addedCompetency.id}"][data-field="name"]`),'介面測試職能');
          assert(addedCompetency.name==='介面測試職能','職能編輯失敗');
          document.querySelector(`[data-del="${addedCompetency.id}"]`).click();
          assert(state.matrix.competencies.length===competencyCount,'職能新增或刪除失敗');
          showTab('m3');
          const transfer = new DataTransfer();
          transfer.items.add(new File(['使用 SQL 整理報表，提升效率 30%。'],'fictional-resume.txt',{type:'text/plain'}));
          document.querySelector('#r-file').files=transfer.files;
          document.querySelector('#r-file').dispatchEvent(new Event('change',{bubbles:true}));
          await wait(()=>document.querySelector('#r-text').value.includes('SQL'));
          document.querySelector('#btn-analyze').click();
          await wait(()=>state.candidates.some(c=>c.result));
          assert(document.querySelector('#ranking').textContent.includes('fictional-resume'),'履歷評分未顯示');
          showTab('m2');
          const moduleOneText = document.querySelector('#m1').textContent;
          const moduleTwoText = document.querySelector('#m2').textContent;
          assert(!moduleOneText.includes('輸入職稱後自動補齊下方空白'),'AI 填寫說明文字仍顯示');
          assert(!moduleTwoText.includes('三項可獨立調整') && !moduleTwoText.includes('總和不必等於 100'),'大類權重冗長說明仍顯示');
          assert(!moduleTwoText.includes('可新增、刪除或修改門檻名稱') && !moduleTwoText.includes('履歷「確定不符合」時的處理'),'門檻輔助說明仍顯示');
          assert(!moduleTwoText.includes('同一批履歷、不同權重') && !moduleTwoText.includes('每個職能 0–3 分。先編輯預設尺度'),'比較或 Rubric 說明文字仍顯示');
          assert(Array.from(document.querySelectorAll('#m2 h2')).some(h=>h.textContent.trim()==='權重組合比較'),'權重組合比較標題遺失');
          await wait(()=>document.querySelector('#preset-compare table'));
          assert(document.querySelectorAll('#preset-compare tbody tr').length===1,'權重組合比較表格未正常顯示');
          assert(document.querySelector('#rubric-default input') && document.querySelector('#apply-rubric') &&
            document.querySelector('#rubric-items input[data-id][data-lv]'),'Rubric 編輯功能遺失');
          assert(!document.querySelector('[data-comp-weight]'),'不應顯示職能權重設定');
          const slider = key => document.querySelector(`[data-w="${key}"]`);
          input(slider('skill'),'26');
          input(slider('soft'),'50');
          assert(state.weights.skill===26 && state.weights.experience===35 && state.weights.soft===50,'大類滑桿不應自動更動其他權重');
          assert(document.querySelector('#weight-total').textContent==='111','權重總和應即時更新為 111');
          assert(document.querySelector('#weight-warning').textContent==='目前總權重為 111，超出 11，請調整至 100。','總和 111 提醒錯誤');
          assert(document.querySelector('#weight-warning').classList.contains('weight-warning') &&
            getComputedStyle(document.querySelector('#weight-warning')).borderLeftColor==='rgb(208, 59, 59)','超額提醒應使用紅色警告樣式');
          let analyzeRequests = 0;
          const originalFetch = window.fetch.bind(window);
          window.fetch = (...args) => {
            if (String(args[0]).includes('/api/resume/analyze')) analyzeRequests++;
            return originalFetch(...args);
          };
          input(document.querySelector('#r-text'),'使用 SQL 製作報表');
          document.querySelector('#btn-analyze').click();
          await wait(()=>document.querySelector('#analyze-msg').textContent.includes('請先調整權重'));
          assert(analyzeRequests===0 && state.candidates.length===1,'權重總和不符時應阻止正式履歷評分');
          const invalidScoreResponse = await originalFetch('/api/score',{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({matrix:state.matrix,weights:state.weights,analyses:[state.candidates[0].analysis]})
          });
          assert(invalidScoreResponse.status===400,'後端應拒絕不等於 100 的正式計分');
          const invalidAnalyzeResponse = await originalFetch('/api/resume/analyze',{
            method:'POST',headers:{'Content-Type':'application/json'},
            body:JSON.stringify({jd:state.jd,matrix:state.matrix,weights:state.weights,resume:'使用 SQL',use_ai:false})
          });
          assert(invalidAnalyzeResponse.status===400,'後端應在無效權重時拒絕履歷分析');
          window.fetch = originalFetch;
          input(slider('skill'),'30');
          input(slider('soft'),'25');
          assert(document.querySelector('#weight-total').textContent==='90','權重總和應即時更新為 90');
          assert(document.querySelector('#weight-warning').textContent==='目前總權重為 90，尚差 10，請調整至 100。','總和 90 提醒錯誤');
          input(slider('skill'),'40');
          assert(document.querySelector('#weight-total').textContent==='100' && document.querySelector('#weight-warning').hidden,'總和 100 時提醒應消失');
          await wait(()=>state.candidates[0].result);
          const previousKnockouts = state.matrix.knockouts.length;
          document.querySelector('#btn-add-knockout').click();
          await wait(()=>state.matrix.knockouts.length===previousKnockouts+1);
          const addedKnockout = state.matrix.knockouts[state.matrix.knockouts.length-1];
          const knockoutName = document.querySelector(`#knockout-settings [data-id="${addedKnockout.id}"][data-field="name"]`);
          input(knockoutName,'測試門檻名稱');
          assert(addedKnockout.name==='測試門檻名稱','門檻名稱編輯失敗');
          const knockoutRequirement = document.querySelector(`#knockout-settings [data-id="${addedKnockout.id}"][data-field="requirement"]`);
          input(knockoutRequirement,'至少三年相關經驗');
          assert(addedKnockout.requirement==='至少三年相關經驗','門檻要求編輯失敗');
          document.querySelector(`#knockout-settings [data-del="${addedKnockout.id}"]`).click();
          await wait(()=>state.matrix.knockouts.length===previousKnockouts);
          assert(!state.matrix.knockouts.some(k=>k.id===addedKnockout.id),'刪除門檻失敗');
          input(document.querySelector('#rubric-items [data-lv]'),'待確認：履歷沒有可核對的證據');
          await wait(()=>state.candidates[0].result.stale);
          document.querySelector('#btn-reanalyze').click();
          await wait(()=>!state.candidates[0].result.stale);
          showTab('m1');
          input(document.querySelector('[data-field="name"]'),'SQL 報表分析');
          await wait(()=>state.candidates[0].result.stale);
          assert(state.candidates[0].result.recommendation==='待人工確認','舊評分未標記');
          assert(window.testErrors.length===0,JSON.stringify(window.testErrors));
          return {passed:true, competencies:state.matrix.competencies.length, candidates:state.candidates.length};
        })()"""
        result = command("Runtime.evaluate", {"expression": script, "awaitPromise": True, "returnByValue": True})
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"])
        print(json.dumps(result["result"].get("value"), ensure_ascii=False))
finally:
    process.terminate()
    process.wait(timeout=20)
