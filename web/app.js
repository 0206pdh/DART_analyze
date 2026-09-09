const companyInput = document.querySelector("#company");
const companySearch = document.querySelector("#company-search");
const companyResult = document.querySelector("#company-result");
const form = document.querySelector("#analysis-form");
const postingUrl = document.querySelector("#posting-url");
const postingUrlImport = document.querySelector("#posting-url-import");
const postingFile = document.querySelector("#posting-file");
const postingImportStatus = document.querySelector("#posting-import-status");
const companySearchState = { query: "", offset: 0, total: 0, loading: false };
const previousRequest = readSessionJson("dartCareerAnalysisRequest");
const sessionReady = ensureSession();

if (previousRequest) {
  companyInput.value = previousRequest.company_name || "";
  companyInput.dataset.corpCode = previousRequest.corp_code || "";
  form.elements.role.value = previousRequest.role || "";
  form.elements.posting.value = previousRequest.job_posting || "";
  form.elements.experience.value = previousRequest.experience || "";
  if (previousRequest.corp_code) {
    companyResult.hidden = false;
    companyResult.innerHTML = `<p class="selected-company"><strong>${escapeHtml(previousRequest.company_name)}</strong> 선택 · DART ${escapeHtml(previousRequest.corp_code)}</p>`;
  }
}

companyInput.addEventListener("input", () => {
  if (companyInput.value !== previousRequest?.company_name) delete companyInput.dataset.corpCode;
});

companyResult.addEventListener("scroll", () => {
  const nearBottom = companyResult.scrollTop + companyResult.clientHeight >= companyResult.scrollHeight - 40;
  if (nearBottom) loadMoreCompanies();
});

companySearch.addEventListener("click", searchCompanies);
postingUrlImport.addEventListener("click", importPostingFromUrl);
postingFile.addEventListener("change", importPostingFromFile);
companyInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    searchCompanies();
  }
});

async function searchCompanies() {
  await sessionReady;
  const name = companyInput.value.trim();
  if (!name) {
    companyInput.focus();
    return;
  }

  companySearchState.query = name;
  companySearchState.offset = 0;
  companySearchState.total = 0;
  companySearch.disabled = true;
  companySearch.textContent = "검색 중";
  companyResult.hidden = false;
  companyResult.innerHTML = '<p class="search-message">기업 원장을 검색하고 있습니다.</p>';

  try {
    const response = await fetch(`/api/companies/search?q=${encodeURIComponent(name)}&limit=20&offset=0`);
    if (!response.ok) throw new Error(`기업 검색 실패 (${response.status})`);
    const data = await response.json();
    companySearchState.offset = data.results.length;
    companySearchState.total = data.total;
    renderCompanyResults(data.results, data, false);
  } catch (error) {
    companyResult.innerHTML = `<p class="search-message error">${escapeHtml(error.message)} · FastAPI 서버로 실행했는지 확인해 주세요.</p>`;
  } finally {
    companySearch.disabled = false;
    companySearch.textContent = "검색";
  }
}

function renderCompanyResults(results, page, append) {
  if (results.length === 0) {
    companyResult.innerHTML = '<p class="search-message">일치하는 기업이 없습니다.</p>';
    return;
  }
  const rows = results.map((company, index) => `
    <button class="company-option" type="button"
      data-corp-code="${escapeHtml(company.corp_code)}">
      <span><strong>${escapeHtml(company.corp_name)}</strong><small>DART ${company.corp_code}</small></span>
      <span class="stock-code">${escapeHtml(company.stock_code || "")}</span>
    </button>
  `).join("");

  if (append) {
    companyResult.querySelector(".load-more")?.remove();
    companyResult.insertAdjacentHTML("beforeend", rows);
  } else {
    companyResult.innerHTML = `<p class="result-count">총 ${page.total.toLocaleString()}개 기업</p>${rows}`;
  }
  if (page.has_more) {
    companyResult.insertAdjacentHTML("beforeend", '<button class="load-more" type="button">더 보기</button>');
  }

  companyResult.querySelectorAll(".company-option").forEach((button) => {
    if (button.dataset.bound === "true") return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => {
      const name = button.querySelector("strong").textContent;
      companyInput.value = name;
      companyInput.dataset.corpCode = button.dataset.corpCode;
      companyResult.innerHTML = `<p class="selected-company"><strong>${escapeHtml(name)}</strong> 선택 · DART ${button.dataset.corpCode}</p>`;
      loadCompanyResearch(button.dataset.corpCode);
    });
  });
  companyResult.querySelector(".load-more")?.addEventListener("click", loadMoreCompanies);
}

async function loadMoreCompanies() {
  if (companySearchState.loading || companySearchState.offset >= companySearchState.total) return;
  companySearchState.loading = true;
  const button = companyResult.querySelector(".load-more");
  if (button) {
    button.disabled = true;
    button.textContent = "불러오는 중";
  }
  try {
    const response = await fetch(`/api/companies/search?q=${encodeURIComponent(companySearchState.query)}&limit=20&offset=${companySearchState.offset}`);
    if (!response.ok) throw new Error(`추가 검색 실패 (${response.status})`);
    const data = await response.json();
    companySearchState.offset += data.results.length;
    renderCompanyResults(data.results, data, true);
  } catch (error) {
    if (button) {
      button.disabled = false;
      button.textContent = "다시 시도";
    }
  } finally {
    companySearchState.loading = false;
  }
}

async function loadCompanyResearch(corpCode) {
  await sessionReady;
  const research = document.querySelector("#company-research");
  research.hidden = false;
  research.innerHTML = '<p class="search-message">기업개황과 최근 정기공시를 불러오고 있습니다.</p>';
  try {
    const response = await fetch(`/api/companies/${corpCode}/refresh`, { method: "POST" });
    if (!response.ok) throw new Error(`공시 조회 실패 (${response.status})`);
    const data = await response.json();
    const profile = data.profile;
    research.innerHTML = `
      <div class="profile-row">
        <span><small>대표자</small><strong>${escapeHtml(profile.ceo_name || "정보 없음")}</strong></span>
        <span><small>설립일</small><strong>${formatDate(profile.established_date)}</strong></span>
        <span><small>결산월</small><strong>${escapeHtml(profile.accounting_month || "-")}월</strong></span>
      </div>
      <div class="filing-list">
        <small>최근 정기공시</small>
        ${data.filings.slice(0, 4).map((filing) => `
          <a href="${filing.viewer_url}" target="_blank" rel="noreferrer">
            <span>${escapeHtml(filing.report_name)}</span><time>${formatDate(filing.receipt_date)}</time>
          </a>
        `).join("") || '<p class="search-message">최근 공시가 없습니다.</p>'}
      </div>
      <div id="financial-summary" class="financial-summary"></div>
    `;
    const period = getFinancialPeriod(data.filings[0]);
    if (period) loadFinancialSummary(corpCode, period.businessYear, period.reportCode);
  } catch (error) {
    research.innerHTML = `<p class="search-message error">${escapeHtml(error.message)}</p>`;
  }
}

function getFinancialPeriod(filing) {
  if (!filing) return null;
  const period = filing.report_name.match(/\((\d{4})\.(\d{2})\)/);
  if (!period) return null;
  let reportCode;
  if (filing.report_name.includes("사업보고서")) reportCode = "11011";
  else if (filing.report_name.includes("반기보고서")) reportCode = "11012";
  else if (filing.report_name.includes("분기보고서") && period[2] === "03") reportCode = "11013";
  else if (filing.report_name.includes("분기보고서") && period[2] === "09") reportCode = "11014";
  if (!reportCode) return null;
  return { businessYear: period[1], reportCode };
}

async function loadFinancialSummary(corpCode, businessYear, reportCode) {
  await sessionReady;
  const container = document.querySelector("#financial-summary");
  container.innerHTML = '<p class="search-message">주요 재무정보를 불러오고 있습니다.</p>';
  try {
    const query = new URLSearchParams({ business_year: businessYear, report_code: reportCode });
    const response = await fetch(`/api/companies/${corpCode}/financials/refresh?${query}`, { method: "POST" });
    if (!response.ok) throw new Error(`재무정보 조회 실패 (${response.status})`);
    const data = await response.json();
    if (data.metrics.length === 0) {
      container.innerHTML = '<p class="search-message">제공되는 구조화 재무정보가 없습니다.</p>';
      return;
    }
    container.innerHTML = `
      <div class="financial-heading"><small>주요 재무정보</small><span>${data.business_year || businessYear} · ${data.financial_statement_division === "CFS" ? "연결" : "개별"}</span></div>
      <div class="metric-grid">
        ${data.metrics.map((metric) => `
          <div class="metric-item">
            <small>${escapeHtml(metric.label)}</small>
            <strong>${formatKoreanAmount(metric.current_amount)}</strong>
            <span class="metric-change ${metric.change_percent > 0 ? "up" : metric.change_percent < 0 ? "down" : ""}">
              ${metric.change_percent === null ? "비교값 없음" : `${metric.change_percent > 0 ? "+" : ""}${metric.change_percent}%`}
            </span>
            <em>${escapeHtml(metric.comparison_basis)}</em>
          </div>
        `).join("")}
      </div>
    `;
  } catch (error) {
    container.innerHTML = `<p class="search-message error">${escapeHtml(error.message)}</p>`;
  }
}

function formatKoreanAmount(value) {
  const amount = Number(value);
  const absolute = Math.abs(amount);
  if (absolute >= 1e12) return `${(amount / 1e12).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}조`;
  if (absolute >= 1e8) return `${(amount / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
  if (absolute >= 1e4) return `${(amount / 1e4).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return amount.toLocaleString("ko-KR");
}

function formatDate(value) {
  if (!value || value.length !== 8) return value || "-";
  return `${value.slice(0, 4)}.${value.slice(4, 6)}.${value.slice(6, 8)}`;
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value);
  return element.innerHTML;
}

async function importPostingFromUrl() {
  const url = postingUrl.value.trim();
  if (!url) {
    postingUrl.focus();
    return;
  }
  setPostingImportState(true, "URL에서 채용공고 본문을 가져오는 중입니다.");
  try {
    const response = await fetch("/api/job-postings/from-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await parseResponse(response);
    if (!response.ok) throw new Error(data.detail || `URL 가져오기 실패 (${response.status})`);
    form.elements.posting.value = data.text;
    setPostingImportState(false, `URL에서 ${data.character_count.toLocaleString()}자 가져왔습니다. 내용을 확인하고 수정해 주세요.`);
  } catch (error) {
    setPostingImportState(false, error.message);
  }
}

async function importPostingFromFile() {
  const file = postingFile.files[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);
  setPostingImportState(true, `${file.name}에서 본문을 읽는 중입니다.`);
  try {
    const response = await fetch("/api/job-postings/from-file", { method: "POST", body: formData });
    const data = await parseResponse(response);
    if (!response.ok) throw new Error(data.detail || `파일 가져오기 실패 (${response.status})`);
    form.elements.posting.value = data.text;
    setPostingImportState(false, `${file.name}에서 ${data.character_count.toLocaleString()}자 가져왔습니다. 내용을 확인하고 수정해 주세요.`);
  } catch (error) {
    setPostingImportState(false, error.message);
  } finally {
    postingFile.value = "";
  }
}

function setPostingImportState(loading, message) {
  postingUrlImport.disabled = loading;
  postingFile.disabled = loading;
  postingImportStatus.textContent = message;
  postingImportStatus.classList.toggle("error", !loading && message.includes("실패"));
}

async function parseResponse(response) {
  try {
    return await response.json();
  } catch {
    return { detail: "서버가 올바른 응답을 반환하지 않았습니다." };
  }
}

function readSessionJson(key) {
  try {
    return JSON.parse(sessionStorage.getItem(key) || "null");
  } catch {
    sessionStorage.removeItem(key);
    return null;
  }
}

async function ensureSession() {
  try {
    const response = await fetch("/api/auth/session", { credentials: "same-origin" });
    return response.ok;
  } catch {
    return false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;

  const data = new FormData(form);
  const company = data.get("company").trim();
  const role = data.get("role").trim();
  const posting = data.get("posting").trim();
  const experience = data.get("experience").trim();
  const corpCode = companyInput.dataset.corpCode;
  if (!corpCode) {
    companyResult.hidden = false;
    companyResult.innerHTML = '<p class="search-message error">검색 결과에서 정확한 상장사를 먼저 선택해 주세요.</p>';
    return;
  }

  sessionStorage.setItem("dartCareerAnalysisRequest", JSON.stringify({
    company_name: company,
    corp_code: corpCode,
    role,
    job_posting: posting,
    experience: experience || null,
  }));
  sessionStorage.removeItem("dartCareerAnalysisResult");
  window.location.href = "/analysis.html";
});
