const requestKey = "dartCareerAnalysisRequest";
const resultKey = "dartCareerAnalysisResult";
const request = JSON.parse(sessionStorage.getItem(requestKey) || "null");

document.querySelector("#retry-button").addEventListener("click", runAnalysis);

if (!request) {
  showError("분석할 지원 정보가 없습니다. 첫 화면에서 기업과 채용공고를 입력해 주세요.", false);
} else {
  const cached = JSON.parse(sessionStorage.getItem(resultKey) || "null");
  if (cached) renderAnalysis(cached);
  else runAnalysis();
}

async function runAnalysis() {
  document.querySelector("#loading-state").hidden = false;
  document.querySelector("#error-state").hidden = true;
  document.querySelector("#result-content").hidden = true;
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
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `분석 실패 (${response.status})`);
    sessionStorage.setItem(resultKey, JSON.stringify(body));
    renderAnalysis(body);
  } catch (error) {
    showError(error.message, true);
  }
}

function renderAnalysis(data) {
  document.querySelector("#loading-state").hidden = true;
  document.querySelector("#error-state").hidden = true;
  document.querySelector("#result-content").hidden = false;
  document.querySelector("#result-company").textContent = data.company_name;
  document.querySelector("#result-meta").textContent = `${data.role} · 공시 근거 ${data.sources.length}개`;
  document.querySelector("#job-summary").textContent = data.result.job_summary;

  document.querySelector("#company-insights").innerHTML = data.result.company_insights.map((item) => `
    <div class="result-item"><p>${escapeHtml(item.statement)}</p></div>`).join("");
  document.querySelector("#connections").innerHTML = data.result.connections.map((item) => `
    <div class="result-item connection-item"><h3>${escapeHtml(item.requirement)}</h3><p>${escapeHtml(item.connection)}</p><small>${escapeHtml(item.company_context)}</small></div>`).join("");
  document.querySelector("#directions").innerHTML = data.result.writing_directions.map((item, index) => `
    <div class="direction-card"><span>${String(index + 1).padStart(2, "0")}</span><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.core_message)}</p><div class="experience-question"><strong>내 경험에 물어볼 것</strong>${escapeHtml(item.experience_prompt)}</div></div>`).join("");
  document.querySelector("#sources").innerHTML = data.sources.map((source, index) => `
    <article class="evidence-item" id="${sourceDomId(source.source_id)}"><span>${String(index + 1).padStart(2, "0")} · ${source.source_type === "filing" ? "공시" : "재무"}</span><h3>${escapeHtml(source.title)}</h3><p>${escapeHtml(source.excerpt.slice(0, 320))}${source.excerpt.length > 320 ? "…" : ""}</p>${source.viewer_url ? `<a href="${source.viewer_url}" target="_blank" rel="noreferrer">DART 원문 열기 ↗</a>` : ""}</article>`).join("");
  document.querySelector("#result-disclaimer").textContent = `${data.disclaimer} · 분석 ID ${data.analysis_id}`;
  window.scrollTo({ top: 0 });
}

function showError(message, retryable) {
  document.querySelector("#loading-state").hidden = true;
  document.querySelector("#result-content").hidden = true;
  document.querySelector("#error-state").hidden = false;
  document.querySelector("#error-message").textContent = message;
  document.querySelector("#retry-button").hidden = !retryable;
}

function sourceDomId(value) { return `source-${value.replace(/[^a-zA-Z0-9_-]/g, "-")}`; }
function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}
