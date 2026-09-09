const requestKey = "dartCareerAnalysisRequest";
const resultKey = "dartCareerAnalysisResult";
const request = readSessionJson(requestKey);
const ANALYSIS_TIMEOUT_MS = 40_000;
let analysisInFlight = false;
let progressTimer = null;
let latestData = null;
const generatedDrafts = {};
const sessionReady = ensureSession();

document.querySelector("#retry-button").addEventListener("click", () => {
  sessionStorage.removeItem(resultKey);
  runAnalysis();
});
document.querySelector("#copy-markdown").addEventListener("click", () => copyMarkdown());
document.querySelector("#download-markdown").addEventListener("click", downloadMarkdown);
document.querySelector("#export-pdf").addEventListener("click", () => window.print());

if (!request) {
  showError("분석할 지원 정보가 없습니다. 첫 화면에서 기업과 채용공고를 입력해 주세요.", false);
} else {
  const cached = readSessionJson(resultKey);
  const cachedData = cached?.signature && cached?.data
    ? cached.signature === requestSignature(request) ? cached.data : null
    : cached;
  if (cachedData?.result) renderAnalysis(cachedData);
  else runAnalysis();
}

async function runAnalysis() {
  if (analysisInFlight || !request) return;
  analysisInFlight = true;
  showLoading();
  await sessionReady;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  try {
    const response = await fetch("/api/analyses", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corp_code: request.corp_code,
        role: request.role,
        job_posting: request.job_posting,
        experience: request.experience,
      }),
      signal: controller.signal,
    });
    const body = await parseResponse(response);
    if (!response.ok) throw new Error(body.detail || `분석 실패 (${response.status})`);
    sessionStorage.setItem(resultKey, JSON.stringify({ signature: requestSignature(request), data: body, savedAt: Date.now() }));
    renderAnalysis(body);
  } catch (error) {
    if (error.name === "AbortError") {
      showError("분석이 40초 안에 완료되지 않았습니다. 잠시 후 다시 시도해 주세요. 같은 요청은 완료된 결과가 있으면 자동으로 재사용됩니다.", true);
    } else {
      showError(error.message, true);
    }
  } finally {
    clearTimeout(timeoutId);
    stopProgress();
    analysisInFlight = false;
  }
}

function showLoading() {
  const loading = document.querySelector("#loading-state");
  loading.hidden = false;
  loading.setAttribute("aria-busy", "true");
  document.querySelector("#error-state").hidden = true;
  document.querySelector("#result-content").hidden = true;
  startProgress();
}

function startProgress() {
  const steps = [...document.querySelectorAll(".loading-steps span")];
  const messages = [
    "최신 보고서에서 직무와 관련된 근거를 선별하는 중입니다.",
    "채용공고의 요구 역량과 기업의 사업 과제를 연결하는 중입니다.",
    "지원자의 경험을 바탕으로 작성 방향을 정리하는 중입니다.",
  ];
  let index = 0;
  const update = () => {
    steps.forEach((step, stepIndex) => step.classList.toggle("active", stepIndex === index));
    document.querySelector("#loading-message").textContent = messages[index];
    index = Math.min(index + 1, steps.length - 1);
  };
  update();
  progressTimer = setInterval(update, 5_000);
}

function stopProgress() {
  if (progressTimer) clearInterval(progressTimer);
  progressTimer = null;
  document.querySelector("#loading-state").setAttribute("aria-busy", "false");
}

function renderAnalysis(data) {
  latestData = data;
  document.querySelector("#loading-state").hidden = true;
  document.querySelector("#error-state").hidden = true;
  document.querySelector("#result-content").hidden = false;
  document.querySelector("#result-company").textContent = data.company_name;
  document.querySelector("#result-meta").textContent = `${data.role} · 근거 ${data.sources.length}개${data.cached ? " · 저장된 결과" : ""}`;
  document.querySelector("#job-summary").textContent = data.result.job_summary;

  const sourceMap = new Map(data.sources.map((source) => [source.source_id, source]));
  document.querySelector("#company-insights").innerHTML = data.result.company_insights.map((item) => `
    <div class="result-item"><div class="result-tags"><span class="kind-tag ${item.kind}">${item.kind === "fact" ? "공시 확인" : "해석"}</span>${renderCitations(item.source_ids, sourceMap)}</div><p>${escapeHtml(item.statement)}</p></div>`).join("");

  const investmentFocus = data.result.investment_focus || [];
  document.querySelector("#investment-focus").innerHTML = investmentFocus.length
    ? `<h3 class="focus-heading">투자·R&amp;D 집중 영역</h3>` + investmentFocus.map((item) => `
      <div class="result-item"><div class="result-tags"><span class="kind-tag ${item.kind}">${item.kind === "fact" ? "공시 확인" : "추론"}</span>${renderCitations(item.source_ids, sourceMap)}</div><p><strong>${escapeHtml(item.area)}</strong> — ${escapeHtml(item.detail)}</p></div>`).join("")
    : "";
  document.querySelector("#connections").innerHTML = data.result.connections.map((item) => `
    <div class="result-item connection-item"><h3>${escapeHtml(item.requirement)}</h3><div class="result-tags">${renderCitations(item.source_ids, sourceMap)}</div><p>${escapeHtml(item.connection)}</p><small>${escapeHtml(item.company_context)}</small></div>`).join("");
  document.querySelector("#directions").innerHTML = data.result.writing_directions.map((item, index) => `
    <div class="direction-card"><span>${String(index + 1).padStart(2, "0")}</span><div class="result-tags">${renderCitations(item.source_ids, sourceMap)}</div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.core_message)}</p><div class="experience-question"><strong>내 경험에 물어볼 것</strong>${escapeHtml(item.experience_prompt)}</div><button class="draft-button" type="button" data-direction-index="${index}">이 방향으로 초안 만들기</button><div class="draft-output" id="draft-${index}" hidden></div></div>`).join("");
  attachDraftButtons(data.result.writing_directions);

  const cautions = data.result.cautions || [];
  document.querySelector("#cautions-section").hidden = !cautions.length;
  document.querySelector("#cautions").innerHTML = cautions.map((item) => `<div class="caution-item">${escapeHtml(item)}</div>`).join("");
  document.querySelector("#sources").innerHTML = data.sources.map((source, index) => `
    <article class="evidence-item" id="${sourceDomId(source.source_id)}"><span>${String(index + 1).padStart(2, "0")} · ${source.source_type === "filing" ? "공시" : "재무"}</span><h3>${escapeHtml(source.title)}</h3><p>${escapeHtml(source.excerpt.slice(0, 320))}${source.excerpt.length > 320 ? "…" : ""}</p>${source.viewer_url ? `<a href="${escapeHtml(source.viewer_url)}" target="_blank" rel="noopener noreferrer">DART 원문 열기 ↗</a>` : ""}</article>`).join("");
  document.querySelector("#result-disclaimer").textContent = `${data.disclaimer} · 분석 ID ${data.analysis_id}`;
  window.scrollTo({ top: 0 });
}

function attachDraftButtons(directions) {
  document.querySelectorAll(".draft-button").forEach((button) => {
    button.addEventListener("click", () => generateDraft(Number(button.dataset.directionIndex), directions[Number(button.dataset.directionIndex)], button));
  });
}

async function generateDraft(index, direction, button) {
  const output = document.querySelector(`#draft-${index}`);
  if (!request.experience || request.experience.trim().length < 20) {
    output.hidden = false;
    output.innerHTML = `<p>초안을 만들려면 먼저 <a href="/">경험 내용을 20자 이상 입력해 주세요.</a></p>`;
    return;
  }
  button.disabled = true;
  button.textContent = "초안 작성 중";
  output.hidden = false;
  output.innerHTML = "<p>입력한 경험을 직무와 연결하고 있습니다.</p>";
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  try {
    await sessionReady;
    const response = await fetch("/api/analyses/draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corp_code: request.corp_code,
        role: request.role,
        job_posting: request.job_posting,
        experience: request.experience,
        direction_title: direction.title,
        direction_message: direction.core_message,
        experience_prompt: direction.experience_prompt,
      }),
      signal: controller.signal,
    });
    const body = await parseResponse(response);
    if (!response.ok) throw new Error(body.detail || `초안 생성 실패 (${response.status})`);
    generatedDrafts[index] = body;
    const sourceMap = new Map(latestData.sources.map((source) => [source.source_id, source]));
    output.innerHTML = `<div class="draft-text">${escapeHtml(body.draft)}</div><p class="draft-feedback"><strong>보완할 점</strong>${escapeHtml(body.feedback)}</p><div class="result-tags">${renderCitations(body.source_ids, sourceMap)}</div>`;
    button.textContent = "초안 다시 만들기";
  } catch (error) {
    output.innerHTML = `<p class="error">${escapeHtml(error.name === "AbortError" ? "초안 생성이 40초 안에 완료되지 않았습니다." : error.message)}</p>`;
    button.textContent = "다시 시도";
  } finally {
    clearTimeout(timeoutId);
    button.disabled = false;
  }
}

function renderCitations(sourceIds = [], sourceMap) {
  return sourceIds.filter((sourceId) => sourceMap.has(sourceId)).map((sourceId) => {
    const source = sourceMap.get(sourceId);
    return `<a class="citation" href="#${sourceDomId(sourceId)}">${source.source_type === "filing" ? "공시" : "재무"} ${sourceNumber(sourceId, latestData?.sources)}</a>`;
  }).join("");
}

function sourceNumber(sourceId, sources = []) {
  const index = sources.findIndex((source) => source.source_id === sourceId);
  return index >= 0 ? index + 1 : "";
}

function toMarkdown(data) {
  const sourceMap = new Map(data.sources.map((source) => [source.source_id, source]));
  const citationText = (ids = []) => ids.filter((id) => sourceMap.has(id)).map((id) => `[${sourceNumber(id, data.sources)}]`).join(" ");
  const lines = [`# ${data.company_name} 지원 전략`, `직무: ${data.role}`, "", "## 핵심 요약", data.result.job_summary, "", "## 기업이 향하는 방향"];
  for (const item of data.result.company_insights) lines.push(`- **${item.kind === "fact" ? "공시 확인" : "해석"}** ${item.statement} ${citationText(item.source_ids)}`);
  if (data.result.investment_focus?.length) {
    lines.push("", "### 투자·R&D 집중 영역");
    for (const item of data.result.investment_focus) lines.push(`- **${item.area}** — ${item.detail} ${citationText(item.source_ids)}`);
  }
  lines.push("", "## 직무와 기업의 연결점");
  for (const item of data.result.connections) lines.push(`### ${item.requirement}\n${item.connection}\n\n> 기업 맥락: ${item.company_context}\n\n${citationText(item.source_ids)}`);
  lines.push("", "## 자기소개서 작성 방향");
  data.result.writing_directions.forEach((item, index) => lines.push(`### ${index + 1}. ${item.title}\n${item.core_message}\n\n- 경험 질문: ${item.experience_prompt}\n- 근거: ${citationText(item.source_ids)}`));
  if (data.result.cautions?.length) lines.push("", "## 주의사항", ...data.result.cautions.map((item) => `- ${item}`));
  const drafts = Object.values(generatedDrafts);
  if (drafts.length) lines.push("", "## 생성한 자기소개서 초안", ...drafts.map((item) => `${item.draft}\n\n보완할 점: ${item.feedback}`));
  lines.push("", "## 출처", ...data.sources.map((source, index) => `${index + 1}. ${source.title} — ${source.report_name || source.source_type}${source.viewer_url ? ` (${source.viewer_url})` : ""}`));
  return lines.join("\n");
}

async function copyMarkdown() {
  if (!latestData) return;
  const markdown = toMarkdown(latestData);
  try {
    await navigator.clipboard.writeText(markdown);
  } catch {
    const area = document.createElement("textarea");
    area.value = markdown;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  flashButton("copy-markdown", "복사 완료");
}

function downloadMarkdown() {
  if (!latestData) return;
  const blob = new Blob([toMarkdown(latestData)], { type: "text/markdown;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${latestData.company_name}-지원전략.md`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function flashButton(id, label) {
  const button = document.querySelector(`#${id}`);
  const original = button.textContent;
  button.textContent = label;
  setTimeout(() => { button.textContent = original; }, 1_500);
}

function showError(message, retryable) {
  document.querySelector("#loading-state").hidden = true;
  document.querySelector("#result-content").hidden = true;
  document.querySelector("#error-state").hidden = false;
  document.querySelector("#error-message").textContent = message;
  document.querySelector("#retry-button").hidden = !retryable;
}

async function parseResponse(response) {
  try { return await response.json(); } catch { return { detail: "서버가 올바른 응답을 반환하지 않았습니다." }; }
}

function requestSignature(value) {
  return JSON.stringify({ corp_code: value.corp_code, role: value.role, job_posting: value.job_posting, experience: value.experience || null });
}

function readSessionJson(key) {
  try { return JSON.parse(sessionStorage.getItem(key) || "null"); } catch { sessionStorage.removeItem(key); return null; }
}

async function ensureSession() {
  try {
    const response = await fetch("/api/auth/session", { credentials: "same-origin" });
    return response.ok;
  } catch {
    return false;
  }
}

function sourceDomId(value) { return `source-${value.replace(/[^a-zA-Z0-9_-]/g, "-")}`; }
function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}
