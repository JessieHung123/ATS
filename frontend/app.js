/* ATS 職能評分教學系統 — 前端（原生 JS，無需建置） */
"use strict";

const GROUPS = { skill: "專業技能", experience: "專案經驗", soft: "軟實力" };
const CATEGORIES = { hard: "硬實力", tools: "工具技能", knowledge: "專業知識", soft: "工作相關軟實力" };
const LEVEL_ICON = { green: "🟢", yellow: "🟡", red: "🔴", info: "⚪" };
const STATUS_TEXT = { met: "✅ 符合", not_met: "❌ 不符合", unknown: "❔ 待確認" };
const STORE_KEY = "ats-teaching-state-v1";
const $ = (sel) => document.querySelector(sel);

let samples = { jobs: [], presets: {}, rubric: [] };
let aiAvailable = false;

const state = loadState() || {
  jobId: null,
  fields: { title: "", years: "", education: "", required: "", bonus: "" },
  jd: "",
  matrix: null,
  matrixSource: "",
  weights: { skill: 40, experience: 35, soft: 25 },
  preset: "balanced",
  candidates: [],
  activeId: null,
  interviews: {},
};
state.uploadedResumes = Array.isArray(state.uploadedResumes) ? state.uploadedResumes : [];

// ---------------- 工具 ----------------
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function uid() { return Math.random().toString(16).slice(2, 10); }
function loadState() {
  try { return JSON.parse(localStorage.getItem(STORE_KEY)); } catch { return null; }
}
let saveTimer;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => localStorage.setItem(STORE_KEY, JSON.stringify(state)), 200);
}
function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}
function useAI() { return $("#use-ai").checked; }

async function api(path, body, isForm = false) {
  const headers = {};
  const model = localStorage.getItem("ats-gemini-model");
  if (model) headers["X-Model"] = model;
  const opts = { method: body ? "POST" : "GET", headers };
  if (body && isForm) opts.body = body;
  else if (body) { headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
  if (path === "/api/job/autofill") opts.signal = AbortSignal.timeout(200000);
  let res;
  try { res = await fetch(path, opts); }
  catch (e) {
    if (path !== "/api/job/autofill") throw e;
    throw new Error(e.name === "TimeoutError" ? "AI 填寫等待逾時，請稍後重試；原有內容已保留。" : "無法連線至 ATS 後端，請確認 8765 服務仍在執行；原有內容已保留。");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `請求失敗（${res.status}）`);
  return data;
}

async function withBusy(btn, msgEl, label, fn) {
  const old = btn.textContent;
  btn.disabled = true;
  btn.textContent = label;
  if (msgEl) msgEl.textContent = "";
  try { await fn(); }
  catch (e) { if (msgEl) msgEl.textContent = "⚠ " + e.message; else alert(e.message); }
  finally { btn.disabled = false; btn.textContent = old; }
}

// ---------------- 初始化 ----------------
async function init() {
  bindTabs();
  bindSettings();
  bindModule1();
  bindModule2();
  bindModule3();
  bindModule4();
  bindTooltip();
  samples = await api("/api/samples");
  state.defaultRubric = state.defaultRubric || [...samples.rubric];
  await refreshStatus();
  renderAll();
}

async function refreshStatus() {
  try {
    const s = await api("/api/status");
    aiAvailable = s.ai_available;
    const sel = $("#model-select");
    if (s.models) {
      sel.innerHTML = Object.entries(s.models)
        .map(([id, label]) => `<option value="${esc(id)}">${esc(label)}</option>`).join("");
      sel.value = s.model;
    }
    const pill = $("#ai-status");
    pill.textContent = aiAvailable ? `此瀏覽器已設定 API Key（${s.model}，尚未驗證）` : "此瀏覽器未設定 API Key：規則式模式";
    pill.className = "pill " + (aiAvailable ? "ai" : "");
    $("#btn-extract").textContent = aiAvailable && useAI() ? "AI 拆解職能" : "拆解職能（規則式）";
  } catch {
    $("#ai-status").textContent = "後端未連線";
  }
}

function bindTabs() {
  $("#tabs").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-tab]");
    if (btn) showTab(btn.dataset.tab);
  });
}
function showTab(id) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === id));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === id));
  if (id === "m2") renderPresetCompare();
  if (id === "m4") renderM4();
}

function bindSettings() {
  $("#save-key").onclick = async () => {
    if ($("#model-select").value) localStorage.setItem("ats-gemini-model", $("#model-select").value);
    await refreshStatus();
    $(".settings").open = false;
  };
  $("#reset-all").onclick = () => {
    if (!confirm("確定清除所有職缺、職能矩陣與候選人資料？（API Key 會保留）")) return;
    localStorage.removeItem(STORE_KEY);
    location.reload();
  };
  $("#use-ai").onchange = refreshStatus;
}

function renderAll() {
  renderM1();
  renderMatrix();
  renderM2();
  renderM3();
}

// ================= 模組 1：職缺 → 職能矩陣 =================
const FIELD_IDS = { title: "f-title", years: "f-years", education: "f-education", required: "f-required", bonus: "f-bonus" };

function jobSignature() { return JSON.stringify([state.fields, state.jd]); }
function jobEdited() {
  invalidateAnalyses();
  $("#job-msg").textContent = "職缺內容已變更，請重新確認並拆解職能。";
  save();
  rescoreSoon();
}
function invalidateAnalyses() {
  state.candidates.forEach((c) => { if (c.analysis) c.analysis.stale = true; });
  state.interviews = {};
}

function bindJobDraft() {
  $("#btn-job-autofill").onclick = (e) => withBusy(e.currentTarget, $("#job-msg"), "AI 填寫中…", async () => {
    // 讀取實際畫面，兼容瀏覽器自動填入但未觸發 input 的情況。
    for (const [k, id] of Object.entries(FIELD_IDS)) state.fields[k] = $("#" + id).value;
    state.jd = $("#f-jd").value;
    if (!state.fields.title.trim()) throw new Error("請先輸入職稱");
    if (!useAI()) throw new Error("請先開啟「使用 AI」");
    if (Object.entries(state.fields).every(([k, v]) => k === "title" || v.trim()) && state.jd.trim()) {
      $("#job-msg").textContent = "所有欄位皆已填寫，沒有需要補齊的空白。";
      return;
    }
    const signature = jobSignature();
    $("#job-msg").textContent = "正在向 Gemini 產生建議草稿，請稍候…";
    $("#ai-status").textContent = "Gemini 請求中…";
    let data;
    try {
      data = await api("/api/job/autofill", { jd: state.jd, fields: state.fields, use_ai: true });
      if (data.source !== "ai" || !["years", "education", "required", "bonus"].every((k) => typeof data.fields?.[k] === "string" && data.fields[k].trim()) || typeof data.jd !== "string" || !data.jd.trim()) {
        throw new Error("API 回傳格式不完整，未套用任何內容。");
      }
    } catch (err) {
      $("#ai-status").textContent = "AI 填寫失敗，請查看下方錯誤";
      $("#ai-status").className = "pill";
      throw err;
    }
    $("#ai-status").textContent = `Gemini 呼叫成功（${data.model || $("#model-select").value}）`;
    $("#ai-status").className = "pill ai";
    if (signature !== jobSignature()) throw new Error("輸入內容已變更，請重新填寫；本次結果未套用。");
    for (const k of ["years", "education", "required", "bonus"]) {
      if (!state.fields[k].trim()) state.fields[k] = data.fields[k];
    }
    if (!state.jd.trim()) state.jd = data.jd;
    state.jobDraft = null;
    state.confirmedJob = null;
    state.autofillNotice = data.notice || "AI 建議草稿，尚待 HR 確認。";
    jobEdited();
    renderM1();
    $("#job-msg").textContent = "AI 已補齊空白欄位，可直接修改或刪除文字；檢查後按「確認目前職缺內容」，再拆解職能。";
  });
  $("#btn-confirm-job").onclick = () => {
    if (!state.jd.trim() && !state.fields.required.trim()) {
      $("#job-msg").textContent = "請先輸入條件，或產生草稿並確認套用。";
      return;
    }
    state.confirmedJob = jobSignature();
    $("#job-msg").textContent = "已確認目前職缺內容，可拆解職能；修改內容後需重新確認。";
    save();
  };
  $("#btn-job-suggest").onclick = (e) => withBusy(e.target, $("#job-msg"), "產生草稿中…", async () => {
    const signature = jobSignature();
    const data = await api("/api/job/suggest", { jd: state.jd, fields: state.fields, use_ai: useAI() });
    if (signature !== jobSignature()) throw new Error("輸入內容已變更，請重新產生草稿。");
    state.jobDraft = { ...data, signature };
    renderJobDraft();
    $("#job-msg").textContent = data.warning || "草稿尚未套用，請逐項審閱。";
  });
  const box = $("#job-draft");
  box.addEventListener("input", (e) => {
    if (e.target.dataset.section) state.jobDraft.draft[e.target.dataset.section][Number(e.target.dataset.index)] = e.target.value;
  });
  box.addEventListener("click", (e) => {
    const el = e.target.closest("button");
    if (!el || !state.jobDraft) return;
    if (el.dataset.draftAdd) state.jobDraft.draft[el.dataset.draftAdd].push("");
    else if (el.dataset.draftDel) state.jobDraft.draft[el.dataset.draftDel].splice(Number(el.dataset.index), 1);
    else if (el.id === "apply-job-draft") {
      if (state.jobDraft.signature !== jobSignature()) {
        $("#job-msg").textContent = "職缺已變更，請重新產生草稿。";
        return;
      }
      const draft = state.jobDraft.draft;
      const lines = Object.entries({ responsibilities: "工作職責", skills: "技能要求", abilities: "工作相關能力" })
        .map(([k,l]) => `【${l}】\n${draft[k].map((v) => v.trim()).filter(Boolean).join("\n")}`);
      if (!Object.values(draft).some((values) => values.some((v) => v.trim()))) {
        $("#job-msg").textContent = "草稿不能全部空白。";
        return;
      }
      // 保留原始 JD 與人資輸入條件；草稿是經人工確認的補充內容。
      state.jd = [state.jd, `【HR 確認的${state.jobDraft.basis === "title" ? "一般建議" : "JD 建議"}】`, ...lines].filter(Boolean).join("\n\n");
      state.confirmedJob = jobSignature();
      state.jobDraft = null;
      invalidateAnalyses();
      rescoreSoon();
      save();
      renderM1();
      $("#job-msg").textContent = "已確認並套用，可拆解職能。";
    }
    renderJobDraft();
  });
}

function renderJobDraft() {
  const box = $("#job-draft"), data = state.jobDraft;
  box.hidden = !data;
  if (!data) { box.innerHTML = ""; return; }
  box.innerHTML = `<p class="callout">${esc(data.notice)}（${data.source === "ai" ? "AI" : "規則式"}草稿）。可新增、刪除與修改；確認後才套用。</p>`
    + Object.entries({ responsibilities: "工作職責", skills: "技能要求", abilities: "工作相關能力" }).map(([k,l]) =>
      `<h3>${l}</h3>${data.draft[k].map((v,i) => `<div class="row"><input style="flex:1;min-width:0" aria-label="${l} ${i+1}" data-section="${k}" data-index="${i}" value="${esc(v)}"><button class="icon-btn" aria-label="刪除${l}" data-draft-del="${k}" data-index="${i}">✕</button></div>`).join("")}<button class="btn small" data-draft-add="${k}">＋ 新增${l}</button>`).join("")
    + '<div class="row"><button class="btn primary" id="apply-job-draft">確認並套用全部草稿</button></div>';
}

function bindModule1() {
  bindJobDraft();
  for (const [k, id] of Object.entries(FIELD_IDS)) {
    $("#" + id).addEventListener("input", (e) => { state.fields[k] = e.target.value; jobEdited(); });
  }
  $("#f-jd").addEventListener("input", (e) => { state.jd = e.target.value; jobEdited(); });

  $("#btn-extract").onclick = (e) => withBusy(e.target, $("#extract-msg"), "拆解中…", async () => {
    if (state.confirmedJob !== jobSignature()) throw new Error("請先確認目前職缺內容，再拆解職能。");
    const signature = jobSignature();
    const data = await api("/api/matrix", { jd: state.jd, fields: state.fields, use_ai: useAI() });
    if (signature !== jobSignature()) throw new Error("職缺已變更，請重新確認並拆解。");
    state.matrix = data.matrix;
    state.matrixJob = signature;
    state.matrixSource = data.source;
    $("#extract-msg").textContent = data.warning ? "⚠ " + data.warning
      : `完成：${data.matrix.competencies.length} 項職能、${data.matrix.knockouts.length} 項門檻。`;
    matrixChanged();
  });

  const editor = $("#matrix-editor");
  editor.addEventListener("input", onMatrixEdit);
  editor.addEventListener("change", onMatrixEdit);
  editor.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    const del = e.target.closest("[data-del]");
    if (add) addMatrixItem(add.dataset.add);
    if (del) {
      const id = del.dataset.del;
      state.matrix.competencies = state.matrix.competencies.filter((c) => c.id !== id);
      state.matrix.knockouts = state.matrix.knockouts.filter((k) => k.id !== id);
      matrixChanged();
    }
  });
}

function renderM1() {
  $("#autofill-notice").hidden = !state.autofillNotice;
  $("#autofill-notice").textContent = state.autofillNotice || "";
  renderJobDraft();
  const box = $("#sample-jobs");
  box.innerHTML = '<span class="muted small">範例職缺：</span>' + samples.jobs
    .map((j) => `<button class="btn small ${state.jobId === j.id ? "active" : ""}" data-job="${j.id}">${esc(j.label)}</button>`).join("");
  box.querySelectorAll("[data-job]").forEach((b) => b.onclick = () => {
    const job = samples.jobs.find((j) => j.id === b.dataset.job);
    state.jobId = job.id;
    state.fields = { ...job.fields };
    state.jd = job.jd;
    jobEdited();
    save();
    renderM1();
  });
  for (const [k, id] of Object.entries(FIELD_IDS)) $("#" + id).value = state.fields[k] || "";
  $("#f-jd").value = state.jd || "";
}

function compRow(c) {
  const imp = `<select data-id="${c.id}" data-field="importance">
      ${["必備", "加分"].map((v) => `<option ${c.importance === v ? "selected" : ""}>${v}</option>`).join("")}</select>`;
  const kw = `<input data-id="${c.id}" data-field="keywords" value="${esc((c.keywords || []).join("、"))}" placeholder="同義詞／關鍵字，以頓號分隔" title="用來在履歷中找佐證的同義詞">`;
  const name = `<input data-id="${c.id}" data-field="name" value="${esc(c.name)}" title="${esc(c.description || "")}">`;
  const del = `<button class="icon-btn" data-del="${c.id}" title="刪除">✕</button>`;
  const category = c.category || (c.type === "soft" ? "soft" : "hard");
  const classification = `<select aria-label="職能類別" data-id="${c.id}" data-field="category">${Object.entries(CATEGORIES).map(([v,l]) => `<option value="${v}" ${category === v ? "selected" : ""}>${l}</option>`).join("")}</select>`;
  const group = `<select aria-label="評分權重大類" data-id="${c.id}" data-field="group">${Object.entries(GROUPS).map(([v,l]) => `<option value="${v}" ${c.group === v ? "selected" : ""}>${l}</option>`).join("")}</select>`;
  return `<div class="competency"><div class="comp-row">${name}${classification}${imp}${kw}${del}</div>
    <label>與職缺的關聯／可評估行為<input data-id="${c.id}" data-field="description" value="${esc(c.description || "")}"></label>
    <label>評分權重大類 ${group}</label></div>`;
}

function koRow(k) {
  const kind = `<select data-id="${k.id}" data-field="kind">
      ${[["years", "年資"], ["education", "學歷"], ["other", "其他"]].map(([v, l]) => `<option value="${v}" ${k.kind === v ? "selected" : ""}>${l}</option>`).join("")}</select>`;
  let param = `<span></span>`;
  if (k.kind === "years") param = `<input type="number" min="0" style="width:4.5rem" data-id="${k.id}" data-field="min_years" value="${k.min_years || 0}" title="最低年資">`;
  if (k.kind === "education") param = `<select data-id="${k.id}" data-field="min_degree">
      ${["不限", "高中", "專科", "學士", "碩士", "博士"].map((d) => `<option ${k.min_degree === d ? "selected" : ""}>${d}</option>`).join("")}</select>`;
  return `<div class="comp-row ko">
    <input data-id="${k.id}" data-field="name" value="${esc(k.name)}">${kind}${param}
    <input data-id="${k.id}" data-field="requirement" value="${esc(k.requirement || "")}" placeholder="JD 原文要求">
    <button class="icon-btn" data-del="${k.id}" title="刪除">✕</button></div>`;
}

function renderMatrix() {
  const m = state.matrix;
  $("#matrix-empty").hidden = !!m;
  $("#matrix-editor").hidden = !m;
  const src = $("#matrix-source");
  src.textContent = m ? (state.matrixSource === "ai" ? "AI 拆解" : "規則式拆解") : "";
  src.className = "pill small " + (state.matrixSource === "ai" ? "ai" : "");
  src.hidden = !m;
  if (!m) return;
  const hard = m.competencies.filter((c) => c.type !== "soft");
  const soft = m.competencies.filter((c) => c.type === "soft");
  $("#list-hard").innerHTML = hard.map(compRow).join("") || '<div class="empty small">無</div>';
  $("#list-soft").innerHTML = soft.map(compRow).join("") || '<div class="empty small">無</div>';
  $("#list-knockout").innerHTML = m.knockouts.map(koRow).join("") || '<div class="empty small">無門檻條件</div>';
}

function findMatrixItem(id) {
  return state.matrix.competencies.find((c) => c.id === id) || state.matrix.knockouts.find((k) => k.id === id);
}

function onMatrixEdit(e) {
  const el = e.target;
  if (!el.dataset.field) return;
  const item = findMatrixItem(el.dataset.id);
  if (!item) return;
  const f = el.dataset.field;
  if (f === "keywords") item.keywords = el.value.split(/[、,，]/).map((s) => s.trim()).filter(Boolean);
  else if (f === "min_years") item.min_years = Number(el.value) || 0;
  else item[f] = el.value;
  if (f === "category") {
    item.type = el.value === "soft" ? "soft" : "hard";
    item.group = el.value === "soft" ? "soft" : "skill";
    if (e.type === "change") renderMatrix();
  }
  if (f === "group") {
    item.type = el.value === "soft" ? "soft" : "hard";
    if (item.type === "soft") item.category = "soft";
    else if (item.category === "soft") item.category = "hard";
    if (e.type === "change") renderMatrix();
  }
  if (f === "kind" && e.type === "change") renderMatrix(); // 切換門檻類型要重畫參數欄
  matrixChanged(false);
}

function addMatrixItem(kind) {
  const rubric = [...(state.defaultRubric || samples.rubric)];
  if (kind === "knockout") {
    state.matrix.knockouts.push({ id: uid(), name: "新門檻", kind: "other", requirement: "", min_years: 0, min_degree: "不限", mode: "deduct", penalty: 15 });
  } else {
    state.matrix.competencies.push({
      id: uid(), name: kind === "soft" ? "新軟實力" : "新技能", type: kind, group: kind === "soft" ? "soft" : "skill",
      importance: "必備", keywords: [], description: "", rubric,
    });
  }
  matrixChanged();
}

const rescoreSoon = debounce(() => rescore(), 300);
function matrixChanged(rerender = true) {
  invalidateAnalyses();
  if (rerender) renderMatrix();
  save();
  renderM2();
  rescoreSoon();
}

// ================= 模組 2：權重與評分標準 =================
function bindModule2() {
  $("#btn-add-knockout").onclick = () => {
    if (state.matrix) addMatrixItem("knockout");
  };
  const knockoutSettings = $("#knockout-settings");
  knockoutSettings.addEventListener("click", (e) => {
    const button = e.target.closest("[data-del]");
    if (!button || !state.matrix) return;
    state.matrix.knockouts = state.matrix.knockouts.filter((k) => k.id !== button.dataset.del);
    matrixChanged();
  });
  knockoutSettings.addEventListener("input", (e) => {
    const el = e.target;
    if (!el.dataset.field || !state.matrix) return;
    const item = state.matrix.knockouts.find((k) => k.id === el.dataset.id);
    if (!item) return;
    item[el.dataset.field] = el.dataset.field === "min_years" ? Math.max(0, Number(el.value) || 0) : el.value;
    invalidateAnalyses();
    renderMatrix();
    save();
    rescoreSoon();
  });
  knockoutSettings.addEventListener("change", (e) => {
    if (e.target.dataset.field === "kind") renderM2();
  });
  $("#apply-rubric").onclick = () => {
    if (!state.matrix) return;
    state.matrix.rubric = [...state.defaultRubric];
    state.matrix.competencies.forEach((c) => (c.rubric = [...state.defaultRubric]));
    invalidateAnalyses();
    rescoreSoon();
    save();
    renderM2();
  };
  $("#rubric-default").addEventListener("input", (e) => {
    state.defaultRubric[Number(e.target.dataset.lv)] = e.target.value;
    save();
  });
  $("#rubric-items").addEventListener("input", (e) => {
    const c = state.matrix.competencies.find((x) => x.id === e.target.dataset.id);
    if (c) { c.rubric[Number(e.target.dataset.lv)] = e.target.value; invalidateAnalyses(); save(); rescoreSoon(); }
  });
}

function setWeight(key, value) {
  const w = state.weights;
  w[key] = Math.max(0, Math.min(100, Math.round(value)));
  state.preset = Object.entries(samples.presets).find(([, p]) => Object.keys(w).every((k) => p.weights[k] === w[k]))?.[0] || "custom";
}

function totalWeight() {
  return Object.keys(GROUPS).reduce((sum, key) => sum + Number(state.weights[key] || 0), 0);
}

function weightWarningMessage() {
  const total = totalWeight();
  if (total === 100) return "";
  const difference = Math.abs(100 - total);
  return total < 100
    ? `目前總權重為 ${total}，尚差 ${difference}，請調整至 100。`
    : `目前總權重為 ${total}，超出 ${difference}，請調整至 100。`;
}

function requireValidWeights(action) {
  const warning = weightWarningMessage();
  if (warning) throw new Error(`${warning} 請先調整權重後再${action}。`);
}

function renderM2() {
  // 預設組合
  $("#presets").innerHTML = Object.entries(samples.presets)
    .map(([k, p]) => `<button class="btn small ${state.preset === k ? "active" : ""}" data-preset="${k}">${esc(p.label)}</button>`).join("")
    + (state.preset === "custom" ? '<span class="pill">自訂</span>' : "");
  $("#presets").querySelectorAll("[data-preset]").forEach((b) => b.onclick = () => {
    state.preset = b.dataset.preset;
    state.weights = { ...samples.presets[b.dataset.preset].weights };
    weightsChanged();
  });

  // 滑桿
  const counts = { skill: 0, experience: 0, soft: 0 };
  (state.matrix?.competencies || []).forEach((c) => counts[c.group]++);
  $("#weight-sliders").innerHTML = Object.entries(GROUPS).map(([k, label]) => `
    <div class="slider-row">
      <div>${label}<span class="count">${counts[k]} 項職能</span></div>
      <input type="range" min="0" max="100" step="1" value="${state.weights[k]}" data-w="${k}" aria-label="${label}權重">
      <div class="val"><span id="wv-${k}">${state.weights[k]}</span></div>
    </div>`).join("") + `<div class="row space small"><span>總權重值</span><b id="weight-total"></b></div>
      <div id="weight-warning" class="warn-box weight-warning" role="alert" aria-live="polite" hidden></div>`;
  renderWeightTotal();
  $("#weight-sliders").querySelectorAll("[data-w]").forEach((s) => s.oninput = () => {
    setWeight(s.dataset.w, Number(s.value));
    for (const k of Object.keys(GROUPS)) {
      $(`[data-w="${k}"]`).value = state.weights[k];
      $("#wv-" + k).textContent = state.weights[k];
    }
    $("#presets").querySelectorAll("[data-preset]").forEach((b) => b.classList.toggle("active", b.dataset.preset === state.preset));
    renderWeightTotal();
    save();
    rescoreSoon();
  });

  // Rubric
  state.defaultRubric = state.defaultRubric || [...samples.rubric];
  $("#rubric-default").innerHTML = state.defaultRubric
    .map((r, i) => `<span class="lv">${i}</span><input data-lv="${i}" value="${esc(r)}">`).join("");
  $("#rubric-items").innerHTML = (state.matrix?.competencies || []).map((c) => `
    <div class="rubric-competency">
      <div class="row space"><b>${esc(c.name)}</b></div>
    <details class="rubric-item"><summary>0–3 分評分尺度 <span class="tag ${c.importance === "必備" ? "must" : ""}">${c.importance}</span>
      <span class="muted small">${GROUPS[c.group]}</span></summary>
      <div class="rubric-edit">${(c.rubric || state.defaultRubric).map((r, i) =>
        `<span class="lv">${i}</span><input data-id="${c.id}" data-lv="${i}" value="${esc(r)}">`).join("")}</div>
    </details></div>`).join("") || '<div class="empty small">尚無職能。</div>';

  // 門檻處理
  const kos = state.matrix?.knockouts || [];
  $("#btn-add-knockout").disabled = !state.matrix;
  $("#knockout-settings").innerHTML = kos.map((k) => `
    <div class="knockout-editor">${koRow(k)}
    <div class="ko-setting">
      <div class="seg" data-ko="${k.id}">
        <button class="${k.mode === "eliminate" ? "on" : ""}" data-mode="eliminate">直接淘汰</button>
        <button class="${k.mode !== "eliminate" ? "on" : ""}" data-mode="deduct">扣分</button>
      </div>
      <label class="small" style="flex-direction:row;align-items:center;margin:0">扣
        <input type="number" min="0" max="100" style="width:4rem" data-penalty="${k.id}" value="${k.penalty ?? 15}" ${k.mode === "eliminate" ? "disabled" : ""}> 分</label>
    </div></div>`).join("") || `<div class="empty small">${state.matrix ? "目前沒有門檻條件，可按「＋ 新增門檻條件」。" : "請先到第一部分拆解職能，再新增門檻條件。"}</div>`;
  $("#knockout-settings").querySelectorAll(".seg button").forEach((b) => b.onclick = () => {
    const k = findMatrixItem(b.parentElement.dataset.ko);
    k.mode = b.dataset.mode;
    save();
    renderM2();
    rescoreSoon();
  });
  $("#knockout-settings").querySelectorAll("[data-penalty]").forEach((i) => i.oninput = () => {
    findMatrixItem(i.dataset.penalty).penalty = Number(i.value) || 0;
    save();
    rescoreSoon();
  });
}

function weightsChanged() {
  save();
  renderM2();
  rescoreSoon();
}

function renderWeightTotal() {
  const total = totalWeight();
  $("#weight-total").textContent = total;
  const warning = $("#weight-warning");
  warning.textContent = weightWarningMessage();
  warning.hidden = !warning.textContent;
}

async function renderPresetCompare() {
  const box = $("#preset-compare");
  const done = state.candidates.filter((c) => c.analysis);
  if (weightWarningMessage()) {
    box.innerHTML = `<div class="warn-box weight-warning" role="alert">${esc(weightWarningMessage())} 權重總和為 100 前，暫停比較評分。</div>`;
    return;
  }
  if (!state.matrix || !done.length) {
    box.innerHTML = '<div class="empty">到「履歷評分」分析至少一份履歷後，這裡會顯示各權重組合下的分數與排名變化。</div>';
    return;
  }
  const analyses = done.map((c) => c.analysis);
  const columns = [["current", "目前設定", state.weights], ...Object.entries(samples.presets).map(([k, p]) => [k, p.label, p.weights])];
  const results = await Promise.all(columns.map(([, , w]) => api("/api/score", { matrix: state.matrix, weights: w, analyses })));
  const ranks = results.map((r) => {
    const order = r.results.map((x, i) => [i, x.eliminated ? -1 : x.total]).sort((a, b) => b[1] - a[1]);
    const rank = {};
    order.forEach(([i], pos) => (rank[i] = pos + 1));
    return rank;
  });
  box.innerHTML = `<table><thead><tr><th>候選人</th>${columns.map(([, l]) => `<th class="num">${esc(l)}</th>`).join("")}</tr></thead><tbody>
    ${done.map((c, i) => `<tr><td>${esc(c.name)}</td>${results.map((r, j) => {
      const x = r.results[i];
      const delta = j > 0 ? ranks[0][i] - ranks[j][i] : 0;
      const arrow = delta > 0 ? `<span class="rank-up">▲${delta}</span>` : delta < 0 ? `<span class="rank-down">▼${-delta}</span>` : "";
      return `<td class="num">${x.eliminated ? "淘汰" : x.total.toFixed(1)} <span class="muted small">#${ranks[j][i]}</span> ${arrow}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table>`;
}

// ================= 模組 3：履歷評分 =================
function bindModule3() {
  $("#r-file").onchange = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (!files.length) return;

    const msg = $("#analyze-msg");
    const failures = [];
    if (!useAI()) {
      msg.className = "warn-box";
      msg.textContent = `已選取 ${files.length} 份履歷，但「使用 AI」未勾選，尚未開始整理。`;
      return;
    }
    if (!aiAvailable) {
      msg.className = "warn-box";
      msg.textContent = `已選取 ${files.length} 份履歷，但此瀏覽器未設定 API Key，尚未送出檔案。請在「設定」儲存金鑰後重試。`;
      return;
    }
    msg.className = "muted small";
    for (const [index, file] of files.entries()) {
      msg.textContent = `AI 整理履歷中（${index + 1}/${files.length}）：${file.name}`;
      const fd = new FormData();
      fd.append("file", file);
      fd.append("use_ai", useAI() ? "true" : "false");
      try {
        const data = await api("/api/resume/parse", fd, true);
        const text = data.extracted_text?.trim();
        if (data.source !== "ai" || !text) {
          throw new Error(data.warnings?.join("；") || "AI 未回傳整理後的履歷");
        }
        const fileLabel = file.name.replace(/\.[^.]+$/, "");
        state.uploadedResumes.push({
          id: uid(),
          name: data.candidate_name?.trim() || `未辨識姓名（${fileLabel}）`,
          text,
          fileName: file.name,
        });
        save();
        renderUploadedResumes();
      } catch (err) {
        failures.push(`${file.name}：${err.message}`);
      }
    }
    const completed = files.length - failures.length;
    msg.textContent = [`AI 已整理 ${completed}/${files.length} 份履歷。`, ...failures].join("\n");
    msg.className = failures.length ? "warn-box" : "muted small";
  };

  $("#uploaded-resumes").addEventListener("click", (e) => {
    const button = e.target.closest("[data-uploaded-resume]");
    if (!button) return;
    const resume = state.uploadedResumes.find((item) => item.id === button.dataset.uploadedResume);
    if (!resume) return;
    $("#r-name").value = resume.name;
    $("#r-text").value = resume.text;
  });

  $("#btn-analyze").onclick = (e) => withBusy(e.target, $("#analyze-msg"), "分析中…", async () => {
    requireValidWeights("進行履歷評分");
    if (!state.matrix) throw new Error("請先到「職缺拆解」產生職能矩陣");
    const text = $("#r-text").value.trim();
    if (!text) throw new Error("請貼上履歷內容");
    const cand = { id: uid(), name: $("#r-name").value.trim(), text };
    await analyzeCandidate(cand);
    state.candidates.push(cand);
    state.activeId = cand.id;
    $("#r-text").value = "";
    $("#r-name").value = "";
    $("#analyze-msg").textContent = cand.analysis.warning ? "⚠ " + cand.analysis.warning
      : `完成（${cand.analysis.source === "ai" ? "AI 評分" : "規則式評分"}）`;
    await rescore();
  });

  $("#btn-reanalyze").onclick = (e) => withBusy(e.target, $("#analyze-msg"), "重新分析中…", async () => {
    requireValidWeights("重新分析履歷");
    for (const c of state.candidates) await analyzeCandidate(c);
    await rescore();
  });

  $("#ranking").addEventListener("click", (e) => {
    const del = e.target.closest("[data-remove]");
    if (del) {
      e.stopPropagation();
      state.candidates = state.candidates.filter((c) => c.id !== del.dataset.remove);
      delete state.interviews[del.dataset.remove];
      if (state.activeId === del.dataset.remove) state.activeId = state.candidates[0]?.id || null;
      save();
      renderM3();
      return;
    }
    const row = e.target.closest("tr[data-cid]");
    if (row) { state.activeId = row.dataset.cid; save(); renderM3(); }
  });
}

async function analyzeCandidate(cand) {
  requireValidWeights("進行履歷評分");
  if (state.matrixJob && state.matrixJob !== jobSignature()) throw new Error("職缺已變更，請確認後重新拆解職能。");
  const weights = { ...state.weights };
  const signature = JSON.stringify([jobSignature(), state.matrix, weights]);
  const data = await api("/api/resume/analyze", { jd: state.jd, matrix: state.matrix, weights, resume: cand.text, use_ai: useAI() });
  if (signature !== JSON.stringify([jobSignature(), state.matrix, state.weights])) throw new Error("分析期間職缺、矩陣或權重已變更，請確認後重新評分。");
  if (weightWarningMessage()) throw new Error(`${weightWarningMessage()} 請先調整權重後重新評分。`);
  cand.analysis = data;
  if (!cand.name) cand.name = data.candidate_name && data.candidate_name !== "未知" ? data.candidate_name : `候選人 ${state.candidates.length + 1}`;
}

async function rescore() {
  const done = state.candidates.filter((c) => c.analysis);
  if (weightWarningMessage()) {
    done.forEach((c) => { c.result = null; });
    save();
    renderM3();
    if ($("#m2").classList.contains("active")) renderPresetCompare();
    return;
  }
  if (state.matrix && done.length) {
    const weights = { ...state.weights };
    try {
      const data = await api("/api/score", { matrix: state.matrix, weights, analyses: done.map((c) => c.analysis) });
      if (weightWarningMessage() || JSON.stringify(weights) !== JSON.stringify(state.weights)) {
        done.forEach((c) => { c.result = null; });
        save();
        renderM3();
        return;
      }
      done.forEach((c, i) => (c.result = data.results[i]));
    } catch (e) { console.error(e); }
  }
  save();
  renderM3();
  if ($("#m2").classList.contains("active")) renderPresetCompare();
}

function sortedCandidates() {
  if (weightWarningMessage()) return [];
  return state.candidates.filter((c) => c.result)
    .sort((a, b) => (a.result.eliminated - b.result.eliminated) || (b.result.total - a.result.total));
}

function renderM3() {
  renderUploadedResumes();
  const ranked = sortedCandidates();
  $("#btn-reanalyze").hidden = !ranked.some((c) => c.result.stale || c.analysis.work_analysis_version !== 2);
  $("#ranking").innerHTML = ranked.length ? `<table>
    <thead><tr><th>#</th><th>候選人</th><th class="num">總分</th><th>建議</th><th class="num">句子品質</th><th></th></tr></thead>
    <tbody>${ranked.map((c, i) => `
      <tr class="clickable ${c.id === state.activeId ? "selected" : ""}" data-cid="${c.id}">
        <td>${i + 1}</td><td>${esc(c.name)} ${c.analysis.source === "ai" ? '<span class="pill ai small">AI</span>' : ""}</td>
        <td class="num"><b>${c.result.total.toFixed(1)}</b></td>
        <td><span class="pill ${c.result.eliminated ? "bad" : c.result.total >= 60 ? "good" : ""}">${esc(c.result.recommendation)}</span></td>
        <td class="num">${c.analysis.stats.quality}%</td>
        <td><button class="icon-btn" data-remove="${c.id}" title="移除">✕</button></td>
      </tr>`).join("")}</tbody></table>
    <p class="muted small">點選列查看詳細報告。共 ${ranked.length} 份，模擬 HR 一次比較多份履歷。</p>`
    : weightWarningMessage()
      ? `<div class="warn-box weight-warning" role="alert">${esc(weightWarningMessage())} 履歷評分已暫停；調整權重後即可繼續。</div>`
      : '<div class="empty">尚無候選人。</div>';
  renderDetail();
}

function renderUploadedResumes() {
  const box = $("#uploaded-resumes");
  box.hidden = !state.uploadedResumes.length;
  box.innerHTML = state.uploadedResumes.length
    ? '<span class="muted small">AI 整理後的履歷：</span>' + state.uploadedResumes
      .map((resume) => `<button type="button" class="btn small" data-uploaded-resume="${esc(resume.id)}" title="${esc(resume.fileName)}">${esc(resume.name)}</button>`).join("")
    : "";
}

function renderDetail() {
  const box = $("#detail");
  if (weightWarningMessage()) {
    box.innerHTML = `<div class="card warn-box weight-warning" role="alert">${esc(weightWarningMessage())} 權重總和為 100 前，不顯示履歷評分結果。</div>`;
    return;
  }
  const c = state.candidates.find((x) => x.id === state.activeId && x.result);
  if (!c || !state.matrix) {
    box.innerHTML = '<div class="card empty">選擇或分析一份履歷，這裡會顯示完整評分報告。</div>';
    return;
  }
  const r = c.result, a = c.analysis, m = state.matrix;
  const items = Object.fromEntries(a.items.map((i) => [i.id, i]));

  const hero = `<div class="card">
    ${r.stale ? '<div class="warn-box">職缺、矩陣或 Rubric 已變更，先前評分待重新確認。請按「全部重新分析」。</div>' : ""}
    ${a.warning ? `<div class="warn-box">${esc(a.warning)}</div>` : ""}
    <div class="score-hero">
      <div class="hero-num">${r.total.toFixed(1)}<small> / 100</small></div>
      <div>
        <h2 style="margin:0">${esc(c.name)} <span class="pill ${r.eliminated ? "bad" : r.total >= 60 ? "good" : ""}">${esc(r.recommendation)}</span>
          <span class="pill small ${a.source === "ai" ? "ai" : ""}">${a.source === "ai" ? "AI 評分" : "規則式評分"}</span></h2>
        <div class="muted small">Match Score = Σ（大類權重 × 大類得分）${r.penalty ? `，原始 ${r.raw_score.toFixed(1)} − 門檻扣分 ${r.penalty}` : ""}。各大類內職能採等權重平均。</div>
        <ul class="ko-list">${r.knockouts.map((k) => `<li>${STATUS_TEXT[k.status]}　<b>${esc(k.name)}</b>
          <span class="muted small">${esc(k.evidence || "")}${k.effect !== "—" ? `｜${esc(k.effect)}` : ""}</span></li>`).join("") || '<li class="muted">無門檻條件</li>'}</ul>
      </div>
    </div></div>`;

  const charts = `<div class="card"><h2>匹配度圖表</h2><div class="charts">
      <div>${radarSVG(m.competencies, items)}</div>
      <div>${groupBars(r)}</div>
    </div></div>`;

  const st = a.stats;
  const legacyWorkAnalysis = a.work_analysis_version !== 2;
  const sentences = `<div class="card"><h2>工作經歷句子分析</h2>
    <p class="muted small">${legacyWorkAnalysis ? "此為舊版工作經歷分析結果，尚未套用修正後的年資計算。" : `${a.sentence_source === "ai" ? "AI 語意分析" : "規則式分析"}；只分析工作經歷，年資依任職日期計算並合併重疊期間（含實習）。`}</p>
    ${a.sentence_warning ? `<div class="warn-box">${esc(a.sentence_warning)}</div>` : ""}
    <p><b>累計工作年資：</b>${esc(legacyWorkAnalysis ? "尚未重新分析" : a.experience_duration || "履歷未提供可計算的工作期間")}</p>
    ${legacyWorkAnalysis ? '<div class="warn-box">按「重新分析全部履歷」更新這份報告；重新分析會將已儲存的履歷內容送至你設定的 AI 服務。</div>' : ""}
    ${!a.work_section_found ? '<div class="empty">找不到工作經歷區段，因此未進行句子評分。請確認履歷內容有「工作經歷」、「工作經驗」或「經歷」標題。</div>' : `
    <div class="legend-row">
      <span>🟢 行動、成果、數據完整 <b>${st.green}</b></span><span>🟡 有行動，仍可補強 <b>${st.yellow}</b></span>
      <span>🔴 描述空泛或缺乏行動 <b>${st.red}</b></span><span class="muted">ℹ 標題／資訊 <b>${st.info}</b></span>
      <span>工作經歷句子品質 <b>${st.quality}%</b></span>
    </div>
    ${a.sentences.length
      ? a.sentences.map((s) => `<div class="sent ${s.level}"><span aria-label="${s.level}">${LEVEL_ICON[s.level]}</span>
        <span>${esc(s.text)}</span><span class="why">${esc(s.reason)}</span></div>`).join("")
      : '<div class="empty">已找到工作經歷區段，但沒有可分析的句子。</div>'}`}
  </div>`;

  const cards = `<div class="card"><h2>職能得分卡</h2><div class="cards">${m.competencies.map((comp) => {
    const it = items[comp.id] || { score: 0, evidence: [], reason: "尚未評分（職能是分析後才新增的）" };
    const rubric = (comp.rubric || m.rubric || [])[it.score] || "";
    return `<div class="score-card">
      <div class="head"><b>${esc(comp.name)}</b><span class="dots" aria-label="${it.score} / 3 分">${"●".repeat(it.score)}<span class="off">${"●".repeat(3 - it.score)}</span> ${it.score}/3</span></div>
      <div><span class="tag ${comp.importance === "必備" ? "must" : ""}">${comp.importance}</span> <span class="tag">${GROUPS[comp.group]}</span></div>
      <div class="rubric-hit">${it.score} 分＝${esc(rubric)}</div>
      ${it.evidence.map((e) => `<blockquote>${esc(e)}</blockquote>`).join("") || '<blockquote class="muted">（履歷中沒有佐證原文）</blockquote>'}
      <div class="reason">${esc(it.reason)}</div></div>`;
  }).join("")}</div></div>`;

  const gaps = `<div class="card"><h2>缺口分析 <span class="muted small">JD 要求但履歷沒證明的項目</span></h2>
    ${r.gaps.length ? `<ul class="gap-list">${r.gaps.map((g) => `<li>
      <span class="tag ${g.importance === "必備" || g.importance === "門檻" ? "must" : ""}">${esc(g.importance)}</span>
      <b>${esc(g.name)}</b><span class="muted small">${esc(g.group)}</span><span>— ${esc(g.issue)}</span></li>`).join("")}</ul>`
      : '<div class="empty">沒有明顯缺口。</div>'}
    <div class="row"><button class="btn" id="goto-iv">針對缺口產生面試問題 →</button></div></div>`;

  box.innerHTML = hero + charts + gaps + cards + sentences;
  $("#goto-iv").onclick = () => { showTab("m4"); $("#iv-candidate").value = c.id; renderInterview(); };
}

// ---------------- 圖表（單一系列：不需圖例） ----------------
function radarSVG(comps, items) {
  if (comps.length < 3) return '<div class="empty small">職能少於 3 項，無法繪製雷達圖。</div>';
  const W = 420, H = 360, cx = W / 2, cy = H / 2 + 4, R = 120, n = comps.length;
  const pt = (i, v) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n;
    return [cx + Math.cos(ang) * R * v, cy + Math.sin(ang) * R * v];
  };
  let g = "";
  for (const lv of [1, 2, 3]) {
    const ring = comps.map((_, i) => pt(i, lv / 3).join(",")).join(" ");
    g += `<polygon points="${ring}" fill="none" stroke="var(--grid)" stroke-width="1"/>`;
  }
  comps.forEach((c, i) => {
    const [x, y] = pt(i, 1);
    const [lx, ly] = pt(i, 1.17);
    const anchor = Math.abs(lx - cx) < 8 ? "middle" : lx > cx ? "start" : "end";
    const label = c.name.length > 9 ? c.name.slice(0, 8) + "…" : c.name;
    g += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="var(--grid)" stroke-width="1"/>`;
    g += `<text x="${lx}" y="${ly + 4}" text-anchor="${anchor}">${esc(label)}</text>`;
  });
  const vals = comps.map((c) => (items[c.id]?.score || 0) / 3);
  const poly = vals.map((v, i) => pt(i, v).join(",")).join(" ");
  g += `<polygon points="${poly}" fill="var(--series-1-soft)" stroke="var(--series-1)" stroke-width="2" stroke-linejoin="round"/>`;
  comps.forEach((c, i) => {
    const [x, y] = pt(i, vals[i]);
    const s = items[c.id]?.score || 0;
    const tip = `${c.name}：${s}/3（${c.importance}）`;
    g += `<circle cx="${x}" cy="${y}" r="4" fill="var(--series-1)" stroke="var(--surface-1)" stroke-width="2"/>`;
    g += `<circle cx="${x}" cy="${y}" r="12" fill="transparent" data-tip="${esc(tip)}"/>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="各職能得分雷達圖（0–3 分）">${g}</svg>
    <div class="muted small" style="text-align:center">各職能得分（外圈 = 3 分）</div>`;
}

function groupBars(r) {
  const rows = Object.entries(GROUPS).map(([k, label]) => {
    const v = r.group_scores[k];
    const w = r.effective_weights[k];
    if (v == null) return `<div class="slider-row"><div>${label}</div><div class="muted small">此大類沒有職能</div><div></div></div>`;
    return `<div class="slider-row" data-tip="${esc(`${label}：${v.toFixed(1)} 分，權重 ${w}%`)}">
      <div>${label}<span class="count">權重 ${w}%</span></div>
      <svg viewBox="0 0 200 18" width="100%" height="18" preserveAspectRatio="none" aria-hidden="true">
        <rect x="0" y="4" width="200" height="10" rx="4" fill="var(--grid)"/>
        ${v > 0 ? `<rect x="0" y="4" width="${Math.max(4, v * 2)}" height="10" rx="4" fill="var(--series-1)"/>` : ""}
      </svg>
      <div class="val">${v.toFixed(1)}</div></div>`;
  }).join("");
  return `<h3>大類得分（0–100）</h3>${rows}
    <div class="muted small">總分 ${r.raw_score.toFixed(1)}${r.penalty ? ` − 扣分 ${r.penalty} = ${r.total.toFixed(1)}` : ""}</div>`;
}

function bindTooltip() {
  const tip = $("#tooltip");
  document.addEventListener("mousemove", (e) => {
    const t = e.target.closest?.("[data-tip]");
    if (!t) { tip.hidden = true; return; }
    tip.textContent = t.getAttribute("data-tip");
    tip.hidden = false;
    tip.style.left = Math.min(e.clientX + 14, innerWidth - 290) + "px";
    tip.style.top = e.clientY + 14 + "px";
  });
}

// ================= 模組 4：面試問題 =================
function bindModule4() {
  $("#iv-candidate").onchange = renderInterview;
  $("#btn-print").onclick = () => window.print();
  $("#btn-interview").onclick = (e) => withBusy(e.target, $("#iv-msg"), "產生中…", async () => {
    requireValidWeights("產生面試問題");
    const c = state.candidates.find((x) => x.id === $("#iv-candidate").value);
    if (!c) throw new Error("請先在「履歷評分」分析至少一份履歷");
    if (c.analysis.stale || c.result?.stale) throw new Error("職缺或評分標準已變更，請先重新分析履歷。");
    const data = await api("/api/interview", {
      jd: state.jd, matrix: state.matrix, weights: state.weights, analysis: c.analysis, resume: c.text, use_ai: useAI(),
    });
    state.interviews[c.id] = data;
    save();
    $("#iv-msg").textContent = data.warning ? "⚠ " + data.warning : `完成（${data.source === "ai" ? "AI 生成" : "範本生成"}）`;
    renderInterview();
  });
}

function renderM4() {
  const ranked = sortedCandidates();
  const sel = $("#iv-candidate");
  const prev = sel.value || state.activeId;
  sel.innerHTML = ranked.map((c) => `<option value="${c.id}">${esc(c.name)}（${c.result.total.toFixed(1)} 分）</option>`).join("")
    || "<option value=''>（尚無候選人）</option>";
  if (ranked.some((c) => c.id === prev)) sel.value = prev;
  renderInterview();
}

function qCard(q, star) {
  return `<div class="q-card">
    <span class="tag must">${esc(q.competency)}</span>
    <div class="q">${esc(q.question)}</div>
    <div class="muted small">為什麼問：${esc(q.why)}</div>
    <div class="cols">
      <div><b>面試官想聽到什麼</b><ul>${q.listen_for.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      <div><b>評分要點</b><ul>${q.scoring.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
    </div>
    ${star ? `<div class="star">${["S", "T", "A", "R"].map((k) => `<div><b>${k}</b>　${esc(q.star[k])}</div>`).join("")}</div>` : ""}
  </div>`;
}

function renderInterview() {
  const id = $("#iv-candidate").value;
  const data = state.interviews[id];
  const c = state.candidates.find((x) => x.id === id);
  if (!data) {
    $("#iv-result").innerHTML = `<div class="card empty">${c ? `按「產生面試問題」為 ${esc(c.name)} 設計題目。` : "尚無候選人。"}</div>`;
    return;
  }
  const sec = (title, desc, list, star) => `<div class="card iv-section"><h2>${title} <span class="muted small">${desc}</span></h2>
    ${list.length ? list.map((q) => qCard(q, star)).join("") : '<div class="empty small">此候選人沒有適合這類的題目。</div>'}</div>`;
  $("#iv-result").innerHTML = `<div class="card"><b>${esc(c?.name || "")}</b>｜${esc(state.matrix?.job_title || "")}
      <span class="pill small ${data.source === "ai" ? "ai" : ""}">${data.source === "ai" ? "AI 生成" : "範本生成"}</span></div>`
    + sec("驗證型", "針對履歷宣稱的成果深挖", data.verification, false)
    + sec("補洞型", "針對得分低的職能提問", data.gap, false)
    + sec("行為面試題", "STAR 結構", data.behavioral, true);
}

init();
