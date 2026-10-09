// Career Assistant — Dashboard Frontend Application Logic (Step 5 Enabled)

(function () {
  let allJobs = [];
  let currentFilter = 'all'; // 'all', 'High', 'Medium', 'Low'
  let currentStatusView = 'REVIEW_PENDING'; // 'all', 'REVIEW_PENDING', 'APPLY_PENDING', 'COVER_LETTER_GENERATED', 'APPLIED', 'SKIPPED'
  let selectedJobIds = new Set();
  let activeJobId = null;
  let bulkPendingAction = null; // 'Apply' or 'Skip'
  let manuallyEditedJobs = new Set(); // Track jobs edited in current session

  // DOM Elements
  const jobListContainer = document.getElementById('job-list-container');
  const selectAllCheckbox = document.getElementById('select-all-checkbox');
  const progressText = document.getElementById('progress-text');
  const progressBarFill = document.getElementById('progress-bar-fill');
  const emptyState = document.getElementById('empty-state');
  const queueSubtitle = document.getElementById('queue-subtitle');
  const searchInput = document.getElementById('search-input');
  const statusViewSelect = document.getElementById('status-view-select');

  // Badges
  const countAll = document.getElementById('count-all');
  const countHigh = document.getElementById('count-high');
  const countMedium = document.getElementById('count-medium');
  const countLow = document.getElementById('count-low');

  // Bulk Bar
  const bulkActionBar = document.getElementById('bulk-action-bar');
  const bulkSelectedCount = document.getElementById('bulk-selected-count');
  const btnBulkPursue = document.getElementById('btn-bulk-pursue');
  const btnBulkSkip = document.getElementById('btn-bulk-skip');
  const btnBulkClear = document.getElementById('btn-bulk-clear');

  // Detail Panel Elements (Right Column)
  const detailPlaceholder = document.getElementById('detail-placeholder');
  const detailPanel = document.getElementById('detail-panel');
  const drawerPrioBadge = document.getElementById('drawer-prio-badge');
  const drawerRoleTitle = document.getElementById('drawer-role-title');
  const drawerCompany = document.getElementById('drawer-company');
  const drawerLocation = document.getElementById('drawer-location');
  const drawerWorkmode = document.getElementById('drawer-workmode');
  const drawerStatus = document.getElementById('drawer-status');
  const drawerUrlLink = document.getElementById('drawer-url-link');
  const drawerSummary = document.getElementById('drawer-summary');
  const drawerMatchesList = document.getElementById('drawer-matches-list');
  const drawerGapsList = document.getElementById('drawer-gaps-list');
  const drawerTrackerNote = document.getElementById('drawer-tracker-note');
  const drawerRawText = document.getElementById('drawer-raw-text');
  const accordionToggle = document.getElementById('accordion-toggle');
  const accordionContent = document.getElementById('accordion-content');
  const drawerBtnSkip = document.getElementById('drawer-btn-skip');
  const drawerBtnPursue = document.getElementById('drawer-btn-pursue');
  const drawerBtnApply = document.getElementById('drawer-btn-apply');

  // Section Containers
  const sectionSummary = document.getElementById('section-summary');
  const sectionMatchesGaps = document.getElementById('section-matches-gaps');
  const cardMatches = document.getElementById('card-matches');
  const cardGaps = document.getElementById('card-gaps');
  const sectionTrackerNote = document.getElementById('section-tracker-note');
  const legacyFullNotice = document.getElementById('legacy-full-notice');

  // Cover Letter Section
  const coverLetterSection = document.getElementById('cover-letter-section');
  const clSourceBadge = document.getElementById('cl-source-badge');
  const clStatusMsg = document.getElementById('cl-status-msg');
  const btnGenerateCl = document.getElementById('btn-generate-cl');
  const clSpinner = document.getElementById('cl-spinner');
  const clEditorGroup = document.getElementById('cl-editor-group');
  const clTextArea = document.getElementById('cl-text-area');
  const btnCopyCl = document.getElementById('btn-copy-cl');
  const btnSaveCl = document.getElementById('btn-save-cl');

  // Bulk Modal
  const bulkModal = document.getElementById('bulk-modal');
  const modalOverlay = document.getElementById('modal-overlay');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnModalCancel = document.getElementById('btn-modal-cancel');
  const btnModalConfirm = document.getElementById('btn-modal-confirm');
  const modalTitle = document.getElementById('modal-title');
  const modalNotice = document.getElementById('modal-notice');
  const modalTableBody = document.getElementById('modal-table-body');

  // Mark Applied Modal Elements
  const applyModal = document.getElementById('apply-modal');
  const applyModalOverlay = document.getElementById('apply-modal-overlay');
  const btnCloseApplyModal = document.getElementById('btn-close-apply-modal');
  const btnCancelApply = document.getElementById('btn-cancel-apply');
  const btnConfirmApply = document.getElementById('btn-confirm-apply');
  const applyRole = document.getElementById('apply-role');
  const applyCompany = document.getElementById('apply-company');
  const applyDate = document.getElementById('apply-date');
  const applyPrio = document.getElementById('apply-prio');
  const applyWorkType = document.getElementById('apply-work-type');
  const applyUrlInput = document.getElementById('apply-url-input');
  const applyNotesInput = document.getElementById('apply-notes-input');

  // Helper to extract clean filename from full path
  function getCleanFileName(fullPath) {
    if (!fullPath) return '';
    return fullPath.split(/[/\\]/).pop();
  }

  function getSgtDateStr() {
    const d = new Date();
    // Convert to SGT (UTC+8)
    const sgtOffsetMs = 8 * 60 * 60 * 1000;
    const utcMs = d.getTime() + (d.getTimezoneOffset() * 60000);
    const sgtDate = new Date(utcMs + sgtOffsetMs);
    return sgtDate.toISOString().split('T')[0];
  }

  function resolveWorkType(facts) {
    if (!facts) return 'Unknown';
    const empMapped = mapWorkType(facts.employment_type);
    if (empMapped !== 'Unknown') return empMapped;
    const modeMapped = mapWorkType(facts.work_mode);
    if (modeMapped !== 'Unknown') return modeMapped;
    return 'Unknown';
  }

  function mapWorkType(rawMode) {
    if (!rawMode) return 'Unknown';
    const str = String(rawMode).trim();
    const allowed = ['Full-time', 'Contract', 'Temporary', 'Part-time', 'Hybrid', 'Remote', 'On-site'];
    if (allowed.includes(str)) return str;

    const lower = str.toLowerCase();
    if (lower.includes('full')) return 'Full-time';
    if (lower.includes('contract')) return 'Contract';
    if (lower.includes('hybrid')) return 'Hybrid';
    if (lower.includes('remote')) return 'Remote';
    if (lower.includes('part')) return 'Part-time';
    if (lower.includes('temp')) return 'Temporary';
    if (lower.includes('on-site') || lower.includes('onsite')) return 'On-site';
    return 'Unknown';
  }


  // Fetch Jobs on Init
  async function fetchJobs() {
    try {
      const res = await fetch('/api/jobs');
      const data = await res.json();
      if (data.success) {
        allJobs = data.jobs;
        renderDashboard();
      }
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    }
  }

  function getFilteredJobs() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    return allJobs.filter((job) => {
      // Filter by Priority Tab
      if (currentFilter !== 'all' && job.recommended_priority !== currentFilter) {
        return false;
      }
      // Filter by Lifecycle Status View
      if (currentStatusView !== 'all' && job.status !== currentStatusView) {
        return false;
      }
      // Filter by Search (role, company, location)
      if (query) {
        const facts = (job.analysis && job.analysis.job) || {};
        const role = (facts.role || '').toLowerCase();
        const company = (facts.company || '').toLowerCase();
        const location = (facts.location || '').toLowerCase();
        if (!role.includes(query) && !company.includes(query) && !location.includes(query)) {
          return false;
        }
      }
      return true;
    });
  }

  function renderDashboard() {
    updateCountsAndProgress();
    const visibleJobs = getFilteredJobs();

    const savedScrollTop = jobListContainer.scrollTop;
    jobListContainer.innerHTML = '';
    selectAllCheckbox.checked = false;

    queueSubtitle.textContent = `Showing ${visibleJobs.length} job${visibleJobs.length === 1 ? '' : 's'}`;

    if (visibleJobs.length === 0) {
      emptyState.classList.remove('hidden');
      const emptyTitle = emptyState.querySelector('.empty-title');
      const emptyDesc = emptyState.querySelector('.empty-desc');
      if (emptyTitle) emptyTitle.textContent = 'No jobs match the current filters.';
      if (emptyDesc) emptyDesc.textContent = 'Try adjusting your search terms, priority, or status filter.';

      detailPanel.classList.add('hidden');
      detailPlaceholder.classList.remove('hidden');
      activeJobId = null;
      updateBulkBar();
      return;
    } else {
      emptyState.classList.add('hidden');
    }

    // Determine active job ID
    let currentActiveInVisible = visibleJobs.find((j) => j.job_id === activeJobId);
    if (!currentActiveInVisible) {
      activeJobId = visibleJobs[0].job_id;
    }

    visibleJobs.forEach((job) => {
      const isChecked = selectedJobIds.has(job.job_id);
      const facts = (job.analysis && job.analysis.job) || {};
      const company = facts.company || 'Company';
      const role = facts.role || 'Role';
      const location = facts.location || 'Singapore';
      const workMode = facts.work_mode ? ` • ${facts.work_mode}` : '';
      const trackerNote = (job.analysis && job.analysis.tracker_note) || job.recommended_action || 'No tracker note available';
      const prio = job.recommended_priority || 'Low';

      const card = document.createElement('div');
      card.className = `job-card ${job.job_id === activeJobId ? 'active' : ''}`;
      card.setAttribute('data-id', job.job_id);

      card.innerHTML = `
        <div class="card-top-row">
          <input type="checkbox" class="card-check" data-id="${job.job_id}" ${isChecked ? 'checked' : ''} onclick="event.stopPropagation()">
          <div class="card-title-group">
            <div class="card-role-title">${escapeHtml(role)}</div>
            <div class="card-company-line">${escapeHtml(company)} <span class="card-meta-inline">• ${escapeHtml(location)}${escapeHtml(workMode)}</span></div>
          </div>
          <span class="prio-badge prio-${prio.toLowerCase()}">${prio}</span>
        </div>
        <div class="card-tracker-note">Tracker: ${escapeHtml(trackerNote)}</div>
        <div class="card-actions-bar" onclick="event.stopPropagation()">
          <div class="status-tags-group">
            <span class="status-tag status-${job.status.toLowerCase()}">${job.status}</span>
            ${job.excel_app_id ? `<span class="excel-slot-badge">${escapeHtml(job.excel_app_id)}</span>` : ''}
          </div>
          <div class="card-action-btns">
            ${job.status === 'REVIEW_PENDING' ? `
              <button class="btn btn-skip btn-sm action-skip" data-id="${job.job_id}">Skip</button>
              <button class="btn btn-pursue btn-sm action-pursue" data-id="${job.job_id}">Pursue</button>
            ` : ''}
            ${(job.status === 'APPLY_PENDING' || job.status === 'COVER_LETTER_GENERATED') ? `
              <button class="btn btn-applied btn-sm action-apply" data-id="${job.job_id}">Mark Applied</button>
            ` : ''}
          </div>
        </div>
      `;

      card.addEventListener('click', () => openDetailPanel(job.job_id));

      const checkbox = card.querySelector('.card-check');
      checkbox.addEventListener('change', (e) => {
        if (e.target.checked) {
          selectedJobIds.add(job.job_id);
        } else {
          selectedJobIds.delete(job.job_id);
        }
        updateBulkBar();
      });

      const btnSkip = card.querySelector('.action-skip');
      if (btnSkip) {
        btnSkip.addEventListener('click', () => handleSingleDecision(job.job_id, 'Skip'));
      }

      const btnPursue = card.querySelector('.action-pursue');
      if (btnPursue) {
        btnPursue.addEventListener('click', () => handleSingleDecision(job.job_id, 'Apply'));
      }

      const btnApply = card.querySelector('.action-apply');
      if (btnApply) {
        btnApply.addEventListener('click', () => openApplyModal(job.job_id));
      }

      jobListContainer.appendChild(card);
    });

    jobListContainer.scrollTop = savedScrollTop;

    if (activeJobId) {
      openDetailPanel(activeJobId);
    } else {
      detailPanel.classList.add('hidden');
      detailPlaceholder.classList.remove('hidden');
    }

    updateBulkBar();
  }


  function openDetailPanel(jobId) {
    activeJobId = jobId;
    const job = allJobs.find((j) => j.job_id === jobId);
    if (!job) {
      detailPanel.classList.add('hidden');
      detailPlaceholder.classList.remove('hidden');
      return;
    }

    // Highlight active card on the left
    document.querySelectorAll('.job-card').forEach((card) => {
      if (card.getAttribute('data-id') === jobId) {
        card.classList.add('active');
      } else {
        card.classList.remove('active');
      }
    });

    const analysis = job.analysis || {};
    const facts = analysis.job || {};

    drawerPrioBadge.textContent = job.recommended_priority || 'Low';
    drawerPrioBadge.className = `prio-badge prio-${(job.recommended_priority || 'low').toLowerCase()}`;
    drawerRoleTitle.textContent = facts.role || 'Role Title';
    drawerCompany.textContent = facts.company || 'Company Name';
    drawerLocation.textContent = facts.location || 'Singapore';
    drawerWorkmode.textContent = facts.work_mode || '-';
    drawerStatus.textContent = job.status;
    drawerUrlLink.href = job.confirmed_url || '#';
    drawerRawText.textContent = job.cleaned_text || 'No raw text available.';

    // Toggle CL-Mode for COVER_LETTER_GENERATED
    if (job.status === 'COVER_LETTER_GENERATED') {
      detailPanel.classList.add('cl-mode');
    } else {
      detailPanel.classList.remove('cl-mode');
    }

    // Single Compact Legacy Notice if ALL 3 analysis fields absent
    const hasSummary = Boolean(analysis.summary && analysis.summary.trim());
    const matches = analysis.key_matches || [];
    const hasMatches = Array.isArray(matches) && matches.length > 0;
    const gaps = analysis.key_gaps || [];
    const hasGaps = Array.isArray(gaps) && gaps.length > 0;

    if (!hasSummary && !hasMatches && !hasGaps) {
      legacyFullNotice.classList.remove('hidden');
      sectionSummary.classList.add('hidden');
      sectionMatchesGaps.classList.add('hidden');
    } else {
      legacyFullNotice.classList.add('hidden');

      if (hasSummary) {
        sectionSummary.classList.remove('hidden');
        drawerSummary.textContent = analysis.summary;
        drawerSummary.className = 'summary-text';
      } else {
        sectionSummary.classList.remove('hidden');
        drawerSummary.textContent = 'Not available in legacy analysis';
        drawerSummary.className = 'summary-text text-muted-italic';
      }

      if (hasMatches || hasGaps) {
        sectionMatchesGaps.classList.remove('hidden');

        drawerMatchesList.innerHTML = '';
        if (hasMatches) {
          matches.forEach((m) => {
            const li = document.createElement('li');
            li.textContent = m;
            drawerMatchesList.appendChild(li);
          });
        } else {
          const li = document.createElement('li');
          li.textContent = 'Not available in legacy analysis';
          li.className = 'text-muted-italic';
          drawerMatchesList.appendChild(li);
        }

        drawerGapsList.innerHTML = '';
        if (hasGaps) {
          gaps.forEach((g) => {
            const li = document.createElement('li');
            li.textContent = g;
            drawerGapsList.appendChild(li);
          });
        } else {
          const li = document.createElement('li');
          li.textContent = 'Not available in legacy analysis';
          li.className = 'text-muted-italic';
          drawerGapsList.appendChild(li);
        }
      } else {
        sectionMatchesGaps.classList.add('hidden');
      }
    }

    // Tracker Note Always Visible Below
    if (analysis.tracker_note && analysis.tracker_note.trim()) {
      drawerTrackerNote.textContent = analysis.tracker_note;
      drawerTrackerNote.className = 'tracker-note-box';
    } else {
      drawerTrackerNote.textContent = 'Not available in legacy analysis';
      drawerTrackerNote.className = 'tracker-note-box text-muted-italic';
    }

    // Reset Accordion
    accordionContent.classList.add('hidden');

    // Handle Footer Action Buttons
    if (job.status === 'REVIEW_PENDING') {
      drawerBtnSkip.classList.remove('hidden');
      drawerBtnPursue.classList.remove('hidden');
      drawerBtnApply.classList.add('hidden');
    } else if (job.status === 'APPLY_PENDING' || job.status === 'COVER_LETTER_GENERATED') {
      drawerBtnSkip.classList.add('hidden');
      drawerBtnPursue.classList.add('hidden');
      drawerBtnApply.classList.remove('hidden');
    } else {
      drawerBtnSkip.classList.add('hidden');
      drawerBtnPursue.classList.add('hidden');
      drawerBtnApply.classList.add('hidden');
    }

    // Handle Cover Letter Section
    coverLetterSection.classList.add('hidden');
    clEditorGroup.classList.add('hidden');
    clSpinner.classList.add('hidden');
    btnGenerateCl.classList.add('hidden');
    clSourceBadge.classList.add('hidden');

    if (job.status === 'APPLY_PENDING') {
      coverLetterSection.classList.remove('hidden');
      clStatusMsg.textContent = 'Status: APPLY_PENDING. Ready to generate tailored cover letter (optional).';
      btnGenerateCl.classList.remove('hidden');
    } else if (job.status === 'COVER_LETTER_GENERATED') {
      coverLetterSection.classList.remove('hidden');
      const cleanFileName = getCleanFileName(job.cover_letter_path);
      clStatusMsg.textContent = `Status: COVER_LETTER_GENERATED (Saved locally: ${cleanFileName})`;

      // Update draft source badge
      clSourceBadge.classList.remove('hidden');
      if (manuallyEditedJobs.has(jobId)) {
        clSourceBadge.textContent = 'Draft source: AI-generated, manually edited';
      } else {
        clSourceBadge.textContent = 'Draft source: AI-generated';
      }

      fetchCoverLetter(jobId);
    }

    detailPlaceholder.classList.add('hidden');
    detailPanel.classList.remove('hidden');
  }

  async function fetchCoverLetter(jobId) {
    try {
      const res = await fetch(`/api/cover-letter/read?job_id=${jobId}`);
      const data = await res.json();
      if (data.success) {
        clTextArea.value = data.content;
        clEditorGroup.classList.remove('hidden');
      } else {
        clStatusMsg.textContent = `Error reading file: ${data.error}`;
      }
    } catch (err) {
      clStatusMsg.textContent = `Fetch error: ${err}`;
    }
  }

  function updateCountsAndProgress() {
    const query = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const statusFiltered = allJobs.filter((job) => {
      if (currentStatusView !== 'all' && job.status !== currentStatusView) {
        return false;
      }
      if (query) {
        const facts = (job.analysis && job.analysis.job) || {};
        const role = (facts.role || '').toLowerCase();
        const company = (facts.company || '').toLowerCase();
        const location = (facts.location || '').toLowerCase();
        if (!role.includes(query) && !company.includes(query) && !location.includes(query)) {
          return false;
        }
      }
      return true;
    });

    countAll.textContent = statusFiltered.length;
    countHigh.textContent = statusFiltered.filter((j) => j.recommended_priority === 'High').length;
    countMedium.textContent = statusFiltered.filter((j) => j.recommended_priority === 'Medium').length;
    countLow.textContent = statusFiltered.filter((j) => j.recommended_priority === 'Low').length;

    const totalReviewable = allJobs.filter((j) => j.status !== 'RETRIEVAL_FAILED').length;
    const decidedJobs = allJobs.filter((j) => j.status !== 'REVIEW_PENDING' && j.status !== 'RETRIEVAL_FAILED');
    progressText.textContent = `${decidedJobs.length} / ${totalReviewable} Decided`;
    const pct = totalReviewable > 0 ? (decidedJobs.length / totalReviewable) * 100 : 0;
    progressBarFill.style.width = `${pct}%`;
  }

  function updateBulkBar() {
    if (selectedJobIds.size > 0) {
      bulkActionBar.classList.remove('hidden');
      bulkSelectedCount.textContent = `${selectedJobIds.size} Job${selectedJobIds.size > 1 ? 's' : ''} Selected`;
    } else {
      bulkActionBar.classList.add('hidden');
    }
  }

  // Handle Select All
  selectAllCheckbox.addEventListener('change', (e) => {
    const visibleJobs = getFilteredJobs();
    if (e.target.checked) {
      visibleJobs.forEach((j) => {
        if (j.status === 'REVIEW_PENDING') selectedJobIds.add(j.job_id);
      });
    } else {
      visibleJobs.forEach((j) => selectedJobIds.delete(j.job_id));
    }
    renderDashboard();
  });

  btnBulkClear.addEventListener('click', () => {
    selectedJobIds.clear();
    renderDashboard();
  });

  // Search Input Listener
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      activeJobId = null;
      renderDashboard();
    });
  }

  // Filter Tabs
  document.querySelectorAll('.tab-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.getAttribute('data-filter');
      activeJobId = null;
      renderDashboard();
    });
  });

  if (statusViewSelect) {
    statusViewSelect.addEventListener('change', (e) => {
      currentStatusView = e.target.value;
      activeJobId = null;
      renderDashboard();
    });
  }


  accordionToggle.addEventListener('click', () => {
    accordionContent.classList.toggle('hidden');
  });

  // Single Job Decision Execution
  async function handleSingleDecision(jobId, decision) {
    try {
      const res = await fetch('/api/jobs/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: jobId, decision: decision }),
      });
      const data = await res.json();
      if (data.success) {
        const visibleJobs = getFilteredJobs();
        const currentIndex = visibleJobs.findIndex((j) => j.job_id === jobId);
        let nextJobId = null;
        if (currentIndex >= 0 && currentIndex + 1 < visibleJobs.length) {
          nextJobId = visibleJobs[currentIndex + 1].job_id;
        } else if (currentIndex > 0) {
          nextJobId = visibleJobs[currentIndex - 1].job_id;
        }

        activeJobId = nextJobId;
        await fetchJobs();
      } else {
        alert(`Decision failed: ${data.error}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    }
  }

  drawerBtnSkip.addEventListener('click', () => {
    if (activeJobId) handleSingleDecision(activeJobId, 'Skip');
  });

  drawerBtnPursue.addEventListener('click', () => {
    if (activeJobId) handleSingleDecision(activeJobId, 'Apply');
  });

  drawerBtnApply.addEventListener('click', () => {
    if (activeJobId) openApplyModal(activeJobId);
  });

  // Mark Applied Modal Logic
  function openApplyModal(jobId) {
    activeJobId = jobId;
    const job = allJobs.find((j) => j.job_id === jobId);
    if (!job) return;

    const analysis = job.analysis || {};
    const facts = analysis.job || {};

    applyRole.textContent = facts.role || 'Role Title';
    applyCompany.textContent = facts.company || 'Company Name';
    applyDate.textContent = getSgtDateStr();
    
    const prio = job.recommended_priority || 'Low';
    applyPrio.textContent = prio;
    applyPrio.className = `prio-badge prio-${prio.toLowerCase()}`;

    applyWorkType.value = resolveWorkType(facts);
    applyUrlInput.value = job.confirmed_url || '';
    applyNotesInput.value = analysis.tracker_note || job.recommended_action || '';

    applyModal.classList.remove('hidden');
  }

  function closeApplyModal() {
    applyModal.classList.add('hidden');
  }

  btnCancelApply.addEventListener('click', closeApplyModal);
  btnCloseApplyModal.addEventListener('click', closeApplyModal);
  applyModalOverlay.addEventListener('click', closeApplyModal);

  btnConfirmApply.addEventListener('click', async () => {
    if (!activeJobId) return;
    btnConfirmApply.disabled = true;
    btnConfirmApply.textContent = 'Writing to Excel...';

    const appUrl = applyUrlInput.value;
    const notes = applyNotesInput.value;
    const workType = applyWorkType.value;

    try {
      const res = await fetch('/api/jobs/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: activeJobId,
          application_url: appUrl,
          notes: notes,
          work_type: workType,
        }),
      });
      const data = await res.json();
      btnConfirmApply.disabled = false;
      btnConfirmApply.textContent = '✓ Confirm & Write Excel';

      if (data.success) {
        closeApplyModal();
        alert(`Application successfully saved to Excel tracker in slot ${data.excel_app_id}!`);
        await fetchJobs();
      } else {
        alert(`Mark Applied Error: ${data.error}`);
      }
    } catch (err) {
      btnConfirmApply.disabled = false;
      btnConfirmApply.textContent = '✓ Confirm & Write Excel';
      alert(`Network error: ${err}`);
    }
  });

  // Cover Letter Generation Event
  btnGenerateCl.addEventListener('click', async () => {
    if (!activeJobId) return;
    btnGenerateCl.classList.add('hidden');
    clSpinner.classList.remove('hidden');
    clStatusMsg.textContent = 'Generating cover letter via GPT-OSS 20B...';

    try {
      const res = await fetch('/api/cover-letter/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: activeJobId }),
      });
      const data = await res.json();
      clSpinner.classList.add('hidden');
      if (data.success) {
        const cleanFileName = getCleanFileName(data.cover_letter_path);
        clStatusMsg.textContent = `Status: COVER_LETTER_GENERATED (Saved locally: ${cleanFileName})`;
        clTextArea.value = data.content;
        clEditorGroup.classList.remove('hidden');
        clSourceBadge.classList.remove('hidden');
        clSourceBadge.textContent = 'Draft source: AI-generated';
        await fetchJobs();
      } else {
        clStatusMsg.textContent = `Generation Error: ${data.error}`;
        btnGenerateCl.classList.remove('hidden');
      }
    } catch (err) {
      clSpinner.classList.add('hidden');
      clStatusMsg.textContent = `Network Error: ${err}`;
      btnGenerateCl.classList.remove('hidden');
    }
  });

  // Save Edits Event
  btnSaveCl.addEventListener('click', async () => {
    if (!activeJobId) return;
    const content = clTextArea.value;
    try {
      const res = await fetch('/api/cover-letter/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: activeJobId, content: content }),
      });
      const data = await res.json();
      if (data.success) {
        manuallyEditedJobs.add(activeJobId);
        clSourceBadge.classList.remove('hidden');
        clSourceBadge.textContent = 'Draft source: AI-generated, manually edited';
        alert('Cover letter edits saved successfully!');
      } else {
        alert(`Save failed: ${data.error}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    }
  });

  btnCopyCl.addEventListener('click', () => {
    navigator.clipboard.writeText(clTextArea.value);
    alert('Cover letter copied to clipboard!');
  });

  // Bulk Actions
  btnBulkPursue.addEventListener('click', () => openBulkModal('Apply'));
  btnBulkSkip.addEventListener('click', () => openBulkModal('Skip'));

  function openBulkModal(decision) {
    bulkPendingAction = decision;
    const selectedJobs = allJobs.filter((j) => selectedJobIds.has(j.job_id));

    modalTitle.textContent = `Confirm Bulk Action: ${decision === 'Apply' ? 'Pursue' : 'Skip'} ${selectedJobs.length} Jobs`;
    modalNotice.textContent = decision === 'Apply'
      ? `The following ${selectedJobs.length} jobs will be set to APPLY_PENDING. Cover letters will NOT be generated automatically and remain individually triggered.`
      : `The following ${selectedJobs.length} jobs will be marked as SKIPPED.`;

    modalTableBody.innerHTML = '';
    selectedJobs.forEach((job) => {
      const tr = document.createElement('tr');
      const facts = (job.analysis && job.analysis.job) || {};
      const role = facts.role || 'Role';
      const company = facts.company || 'Company';
      const prio = job.recommended_priority || 'Low';
      const recAct = job.recommended_action || '-';
      const note = (job.analysis && job.analysis.tracker_note) || '';

      tr.innerHTML = `
        <td class="col-checkbox"><input type="checkbox" class="modal-job-check" data-id="${job.job_id}" checked></td>
        <td class="col-prio"><span class="prio-badge prio-${prio.toLowerCase()}">${prio}</span></td>
        <td class="col-role">${escapeHtml(role)} <br><small class="company-sub">${escapeHtml(company)}</small></td>
        <td class="col-note"><small class="company-sub">Rec: ${recAct}</small><br>${escapeHtml(note)}</td>
      `;

      modalTableBody.appendChild(tr);
    });

    bulkModal.classList.remove('hidden');
  }

  function closeBulkModal() {
    bulkModal.classList.add('hidden');
    bulkPendingAction = null;
  }

  btnModalCancel.addEventListener('click', closeBulkModal);
  btnCloseModal.addEventListener('click', closeBulkModal);
  modalOverlay.addEventListener('click', closeBulkModal);

  btnModalConfirm.addEventListener('click', async () => {
    const confirmedChecks = modalTableBody.querySelectorAll('.modal-job-check:checked');
    const confirmedIds = Array.from(confirmedChecks).map((c) => c.getAttribute('data-id'));

    if (confirmedIds.length === 0) {
      alert('No jobs selected in modal.');
      return;
    }

    try {
      const res = await fetch('/api/jobs/bulk-decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_ids: confirmedIds, decision: bulkPendingAction }),
      });
      const data = await res.json();
      if (data.success) {
        selectedJobIds.clear();
        closeBulkModal();
        await fetchJobs();
      } else {
        alert(`Bulk action failed: ${data.error}`);
      }
    } catch (err) {
      alert(`Network error: ${err}`);
    }
  });

  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Initialize
  fetchJobs();
})();
