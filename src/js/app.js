const stateTree = document.getElementById('stateTree');
const rightPanel = document.getElementById('rightPanel');
const searchInput = document.getElementById('searchInput');
const autocompleteDiv = document.getElementById('autocomplete');
const searchBtn = document.getElementById('searchBtn');

// Build state list
const statesSorted = Object.values(JURISDICTIONS).sort((a,b) => a.name.localeCompare(b.name));

function buildTree() {
  stateTree.innerHTML = '';
  statesSorted.forEach(state => {
    const cities = Object.keys(state.cities || {});
    const counties = Object.keys(state.counties || {});
    const hasChildren = cities.length > 0 || counties.length > 0;

    const item = document.createElement('div');
    item.className = 'state-item';

    const primaryCode = Object.keys(state.adopted)[0];
    const primaryYear = primaryCode ? (state.adopted[primaryCode].year || '—') : '—';

    item.innerHTML = `
      <div class="state-row" data-state="${state.abbr}">
        <span class="state-chevron ${hasChildren ? '' : 'hidden'}" id="chev-${state.abbr}">${hasChildren ? '▶' : ' '}</span>
        <span class="state-abbr">${state.abbr}</span>
        <span class="state-name">${state.name}</span>
        ${primaryCode ? `<span class="code-badge badge-blue">${primaryCode}</span>` : ''}
      </div>
      ${hasChildren ? `<div class="sub-items" id="sub-${state.abbr}">
        ${cities.map(city => `<div class="sub-item" data-state="${state.abbr}" data-city="${city}"><span class="sub-icon">🏙</span>${city}</div>`).join('')}
        ${counties.map(county => `<div class="sub-item" data-state="${state.abbr}" data-county="${county}"><span class="sub-icon">🏛</span>${county}</div>`).join('')}
      </div>` : ''}
    `;

    stateTree.appendChild(item);
  });

  // Event listeners
  stateTree.querySelectorAll('.state-row').forEach(row => {
    row.addEventListener('click', (e) => {
      const abbr = row.dataset.state;
      const chev = document.getElementById(`chev-${abbr}`);
      const sub = document.getElementById(`sub-${abbr}`);
      if (sub) {
        sub.classList.toggle('open');
        if (chev) chev.classList.toggle('open');
      }
      showReport(JURISDICTIONS[abbr], null, null);
    });
  });

  stateTree.querySelectorAll('.sub-item').forEach(item => {
    item.addEventListener('click', (e) => {
      e.stopPropagation();
      const abbr = item.dataset.state;
      const city = item.dataset.city;
      const county = item.dataset.county;
      const state = JURISDICTIONS[abbr];
      if (city) showReport(state, state.cities[city], city);
      else if (county) showReport(state, state.counties[county], county);
    });
  });
}

// ─── SEARCH AUTOCOMPLETE ───
function buildSuggestions(query) {
  if (!query || query.length < 2) return [];

  // Split on commas so address inputs like "123 Main St, Phoenix, AZ 85001"
  // are broken into searchable tokens. Strip leading/trailing whitespace and
  // trailing zip codes (e.g. "AZ 85001" → "AZ") from each token.
  const rawParts = query.split(',').map(p => p.trim().replace(/\s+\d{5}(-\d{4})?$/, '').trim());
  // De-duplicate and drop tokens that are too short or look like a street number/name only
  const terms = [...new Set(rawParts)].filter(p => p.length >= 2);

  const results = [];
  const seen = new Set();

  terms.forEach(term => {
    const t = term.toLowerCase();
    Object.values(JURISDICTIONS).forEach(state => {
      if (state.name.toLowerCase().includes(t) || state.abbr.toLowerCase() === t) {
        const key = `state:${state.abbr}`;
        if (!seen.has(key)) {
          seen.add(key);
          results.push({ label: state.name, sub: state.abbr, type: 'STATE', state: state.abbr, city: null, county: null });
        }
      }
      Object.keys(state.cities || {}).forEach(city => {
        if (city.toLowerCase().includes(t)) {
          const key = `city:${state.abbr}:${city}`;
          if (!seen.has(key)) {
            seen.add(key);
            results.push({ label: city, sub: state.name, type: 'CITY', state: state.abbr, city, county: null });
          }
        }
      });
      Object.keys(state.counties || {}).forEach(county => {
        if (county.toLowerCase().includes(t)) {
          const key = `county:${state.abbr}:${county}`;
          if (!seen.has(key)) {
            seen.add(key);
            results.push({ label: county, sub: state.name, type: 'COUNTY', state: state.abbr, city: null, county });
          }
        }
      });
    });
  });

  return results.slice(0, 8);
}

searchInput.addEventListener('input', () => {
  const suggestions = buildSuggestions(searchInput.value);
  if (suggestions.length === 0) {
    autocompleteDiv.classList.remove('visible');
    return;
  }
  autocompleteDiv.innerHTML = suggestions.map((s, i) => `
    <div class="autocomplete-item" data-index="${i}">
      <span>${s.label} <span style="color:var(--text3);font-size:10px">— ${s.sub}</span></span>
      <span class="item-type">${s.type}</span>
    </div>
  `).join('');

  autocompleteDiv._suggestions = suggestions;
  autocompleteDiv.classList.add('visible');

  autocompleteDiv.querySelectorAll('.autocomplete-item').forEach(item => {
    item.addEventListener('click', () => {
      const idx = parseInt(item.dataset.index);
      const s = autocompleteDiv._suggestions[idx];
      selectSuggestion(s);
    });
  });
});

function selectSuggestion(s) {
  autocompleteDiv.classList.remove('visible');
  const state = JURISDICTIONS[s.state];
  searchInput.value = s.label;
  if (s.city) showReport(state, state.cities[s.city], s.city);
  else if (s.county) showReport(state, state.counties[s.county], s.county);
  else showReport(state, null, null);
}

searchBtn.addEventListener('click', () => {
  const sugg = buildSuggestions(searchInput.value);
  if (sugg.length > 0) selectSuggestion(sugg[0]);
});

searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    const sugg = buildSuggestions(searchInput.value);
    if (sugg.length > 0) selectSuggestion(sugg[0]);
  }
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-wrapper')) {
    autocompleteDiv.classList.remove('visible');
  }
});

// ─── REPORT RENDERER ───
function codeStatusBadge(code) {
  if (code.status === 'own-code') return '<span class="code-badge badge-purple">PROPRIETARY</span>';
  if (code.status === 'adopted') return '<span class="code-badge badge-green">ADOPTED</span>';
  return '<span class="code-badge badge-gray">PENDING</span>';
}

function amendmentIcon(amend) {
  if (amend.toLowerCase().startsWith('based on') || amend.toLowerCase().startsWith('chapter')) return '<span class="amend-icon amend-mod">◈</span>';
  if (amend.toLowerCase().includes('required') || amend.toLowerCase().includes('mandatory')) return '<span class="amend-icon amend-add">+</span>';
  if (amend.toLowerCase().includes('prohibited') || amend.toLowerCase().includes('removed')) return '<span class="amend-icon amend-del">−</span>';
  return '<span class="amend-icon amend-mod">◈</span>';
}

function renderCodeCard(key, code, stateAbbr) {
  const def = CODES[key] || { label: key, name: key, org: '—', color: 'gray' };
  const hasAmendments = code.amendments && code.amendments.length > 0;
  const badgeColor = `badge-${def.color}`;

  // Resolve source URL for this code
  const sourceKey = CODE_SOURCES[key];
  const sourceDef = sourceKey ? DATA_SOURCES[sourceKey] : null;
  let sourceUrl = sourceDef ? sourceDef.url : null;
  // For IECC, prefer the per-state DOE BECP page when we have a state abbreviation
  if (key === 'IECC' && stateAbbr && DATA_SOURCES.becp.stateUrl) {
    sourceUrl = DATA_SOURCES.becp.stateUrl(stateAbbr);
  }
  const sourceHtml = sourceUrl
    ? `<a href="${sourceUrl}" target="_blank" rel="noopener noreferrer"
          class="source-link-icon" title="Source: ${sourceDef.label}">↗</a>`
    : '';

  return `
    <div class="code-card">
      <div class="code-card-header">
        <div>
          <div class="code-name">${def.label}</div>
          <div class="code-full-name">${def.name}</div>
        </div>
        <div style="display:flex;align-items:flex-start;gap:8px">
          ${sourceHtml}
          <div class="code-year">${code.year || '—'}</div>
        </div>
      </div>
      <div class="code-meta-row">
        ${codeStatusBadge(code)}
        <span class="code-badge ${badgeColor}">${def.org}</span>
        <span class="code-badge badge-gray" style="font-size:9px">${code.effective || '—'}</span>
      </div>
      <div class="amendments-section">
        <div class="amendments-label">Local Amendments (${code.amendments ? code.amendments.length : 0})</div>
        ${hasAmendments
          ? code.amendments.map(a => `<div class="amendment-item">${amendmentIcon(a)}<span>${a}</span></div>`).join('')
          : '<div class="no-amendments">No local amendments on record.</div>'
        }
      </div>
    </div>
  `;
}

function buildSourcesPanel(state, isLocal, adoptedCodes) {
  // Collect which source keys are relevant for the codes in this view
  const neededSources = new Set();

  Object.keys(adoptedCodes).forEach(codeKey => {
    const sk = CODE_SOURCES[codeKey];
    if (sk) neededSources.add(sk);
    // IECC also draws from the DOE BECP per-state portal
    if (codeKey === 'IECC') neededSources.add('becp');
  });

  // ICC chart covers most I-codes; always include it if any ICC code is present
  const hasIccCode = Object.keys(adoptedCodes).some(k => DATA_SOURCES.icc_chart.codes.includes(k));
  if (hasIccCode) neededSources.add('icc_chart');

  // For local views (city/county), Municode is a primary source
  if (isLocal) neededSources.add('municode');

  const rows = Array.from(neededSources).map(sk => {
    const src = DATA_SOURCES[sk];
    if (!src) return '';

    // Build URL — for BECP, use the per-state deep-link
    let url = src.url;
    if (sk === 'becp' && src.stateUrl && state.abbr) {
      url = src.stateUrl(state.abbr);
    }
    const urlDisplay = url.replace(/^https?:\/\//, '');

    // Which adopted codes does this source cover in the current view?
    const relevantCodes = Object.keys(adoptedCodes).filter(k => src.codes.includes(k));
    const codeTagsHtml = relevantCodes.length
      ? `<div class="source-codes">covers: ${relevantCodes.join(', ')}</div>`
      : (sk === 'municode' ? `<div class="source-codes">local ordinances &amp; municipal code of ordinances</div>` : '');

    return `
      <div class="source-row">
        <span class="source-icon">${src.icon}</span>
        <div class="source-info">
          <div class="source-label">
            ${src.label}
            <span style="font-family:var(--mono);font-size:9px;color:var(--text3)">${src.note}</span>
          </div>
          <div class="source-url">${urlDisplay}</div>
          ${codeTagsHtml}
        </div>
        <a href="${url}" target="_blank" rel="noopener noreferrer" class="source-open-btn">OPEN ↗</a>
      </div>
    `;
  }).join('');

  return `
    <div class="sources-panel">
      <div class="sources-panel-header">
        <span>Data Sources</span>
        <span style="background:var(--border);padding:2px 7px;border-radius:10px;color:var(--text2)">${neededSources.size}</span>
      </div>
      ${rows}
      <div class="disclaimer-text">
        <strong>⚠ DISCLAIMER:</strong> This database is for reference only. Adoption status changes frequently.
        Always verify current adopted codes and amendments directly with the Authority Having Jurisdiction (AHJ)
        before submitting construction documents. Code adoption varies significantly even within a single county.
      </div>
    </div>
  `;
}

function showReport(state, local, localName) {
  let html = '';

  // Breadcrumb
  const isLocal = local && localName;
  const breadcrumb = isLocal
    ? `<div class="breadcrumb"><span>US</span><span class="breadcrumb-sep">›</span><span>${state.name}</span><span class="breadcrumb-sep">›</span><span class="breadcrumb-active">${localName}</span></div>`
    : `<div class="breadcrumb"><span>US</span><span class="breadcrumb-sep">›</span><span class="breadcrumb-active">${state.name}</span></div>`;

  const displayName = isLocal ? localName : state.name;
  const jType = isLocal ? (local.type || 'municipality').toUpperCase() : 'STATE';
  const adoptedCodes = isLocal ? local.adopted : state.adopted;
  const codeCount = Object.keys(adoptedCodes).length;
  const amendCount = Object.values(adoptedCodes).reduce((sum, c) => sum + (c.amendments?.length || 0), 0);

  const note = isLocal ? local.note : null;
  const fireDistricts = isLocal ? (local.fireDistricts || []) : [];

  // Stats
  const statCards = `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">Codes Adopted</div>
        <div class="stat-value">${codeCount}</div>
        <div class="stat-sub">code books</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Local Amendments</div>
        <div class="stat-value">${amendCount}</div>
        <div class="stat-sub">recorded modifications</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AHJ Type</div>
        <div class="stat-value" style="font-size:14px">${jType}</div>
        <div class="stat-sub">${state.region}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Fire Districts</div>
        <div class="stat-value">${fireDistricts.length}</div>
        <div class="stat-sub">on record</div>
      </div>
    </div>
  `;

  // State note / hierarchy
  const hierNote = `
    <div class="hierarchy-note">
      <strong>AHJ Note:</strong> ${state.stateNote}${note ? '<br><strong>Local Note:</strong> ' + note : ''}
    </div>
  `;

  // Amendment banner
  const hasMajorAmendments = amendCount > 3;
  const amendBanner = hasMajorAmendments
    ? `<div class="amendment-banner">⚠ This jurisdiction has ${amendCount} recorded local amendments. Verify all amendments directly with the building department before submitting plans.</div>`
    : '';

  // Code cards
  const codes_html = Object.entries(adoptedCodes).map(([k,v]) => renderCodeCard(k,v,state.abbr)).join('');

  // Fire district section
  let fireHtml = '';
  if (fireDistricts.length > 0) {
    fireHtml = `<div class="fire-section">
      <div class="section-header">
        <span class="section-title">🔥 Fire Districts / Fire Marshal AHJ</span>
        <span class="section-tag">${fireDistricts.length} DISTRICT(S) ON RECORD</span>
      </div>
      ${fireDistricts.map(fd => `
        <div class="code-card" style="margin-bottom:10px;border-left:2px solid var(--red)">
          <div class="code-name" style="margin-bottom:8px">${fd.name}</div>
          ${Object.entries(fd.adopted).map(([k,v]) => `
            <div style="font-family:var(--mono);font-size:11px;color:var(--text2);margin-bottom:4px">
              <span class="code-badge badge-red" style="margin-right:6px">${k}</span>
              ${v.year ? `<span style="color:var(--accent)">${v.year}</span>` : ''}
            </div>
            <div class="amendments-section">
              <div class="amendments-label">Fire Marshal Amendments</div>
              ${(v.amendments||[]).length ? v.amendments.map(a => `<div class="amendment-item">${amendmentIcon(a)}<span>${a}</span></div>`).join('') : '<div class="no-amendments">No local amendments on record.</div>'}
            </div>
          `).join('')}
        </div>
      `).join('')}
    </div>`;
  }

  // State codes section (if local is shown, add state hierarchy note)
  let stateCodeNote = '';
  if (isLocal && Object.keys(state.adopted).length > 0) {
    stateCodeNote = `
      <div class="section-header" style="margin-top:24px">
        <span class="section-title">⬆ State-Level Base Codes</span>
        <span class="section-tag">INHERITED UNLESS LOCALLY OVERRIDDEN</span>
      </div>
      <div style="font-size:11px;color:var(--text3);margin-bottom:14px;line-height:1.6;">
        Local codes supersede state codes where adopted. For items not covered by local ordinance, state codes apply.
      </div>
      <div class="codes-grid">
        ${Object.entries(state.adopted).map(([k,v]) => renderCodeCard(k,v,state.abbr)).join('')}
      </div>
    `;
  }

  // Data sources footer — collect codes from both local and state-level adoptions
  const allAdoptedForSources = isLocal ? { ...state.adopted, ...local.adopted } : adoptedCodes;
  const footer = buildSourcesPanel(state, isLocal, allAdoptedForSources);

  html = `
    <div class="report-header">
      ${breadcrumb}
      <div class="report-title">
        ${displayName}
        <span class="jurisdiction-type-badge">${jType}</span>
      </div>
      <div class="report-meta">
        <span>📍 ${state.name}</span>
        <span>🗺 ${state.region}</span>
        ${isLocal ? `<span>🏛 ${state.name} state codes also apply</span>` : ''}
      </div>
    </div>
    ${statCards}
    ${hierNote}
    ${amendBanner}
    <div class="section-header">
      <span class="section-title">📋 Adopted Code Books</span>
      <span class="section-tag">${codeCount} CODES ON RECORD</span>
    </div>
    <div class="codes-grid">${codes_html}</div>
    ${fireHtml}
    ${stateCodeNote}
    ${footer}
  `;

  rightPanel.innerHTML = html;
  rightPanel.scrollTop = 0;
}

// Initialize
buildTree();
