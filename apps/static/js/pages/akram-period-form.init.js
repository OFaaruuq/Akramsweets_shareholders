/*
Akram Sweets — Monthly period entry (profit calculation)
*/

(function () {
  const config = window.AKRAM_PERIOD_FORM || {};
  const form = document.getElementById('period-create-form');
  if (!form) return;

  const entryMode = document.getElementById('entry-mode');
  const breakdownFields = document.getElementById('breakdown-fields');
  const manualFields = document.getElementById('manual-fields');
  const computedNetDisplay = document.getElementById('computed-net-display');
  const previewBtn = document.getElementById('preview-distribution-btn');
  const previewCard = document.getElementById('preview-card');
  const previewBody = document.getElementById('preview-table-body');
  const previewCompanyTotal = document.getElementById('preview-company-total');
  const previewTypeBadge = document.getElementById('preview-type-badge');
  const previewReconcile = document.getElementById('preview-reconcile');
  const previewError = document.getElementById('preview-error');
  const warningsBox = document.getElementById('period-warnings');

  const currency = (value) => {
    const amount = Number(value) || 0;
    const formatted = Math.abs(amount).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return (amount < 0 ? '-$' : '$') + formatted;
  };

  const parseNumber = (id) => {
    const el = document.getElementById(id);
    if (!el) return 0;
    const value = parseFloat(el.value);
    return Number.isFinite(value) ? value : 0;
  };

  function toggleEntryMode() {
    const isManual = entryMode && entryMode.value === 'manual';
    breakdownFields.classList.toggle('d-none', isManual);
    manualFields.classList.toggle('d-none', !isManual);
    updateComputedNet();
  }

  function updateComputedNet() {
    if (!computedNetDisplay || entryMode.value === 'manual') return;
    const net =
      parseNumber('total-revenues') -
      parseNumber('cost-of-goods') -
      parseNumber('total-expenses') +
      parseNumber('other-income');
    computedNetDisplay.textContent = currency(net);
    computedNetDisplay.className = 'mt-2 fs-18 fw-semibold ' + (net >= 0 ? 'akram-net-positive' : 'akram-net-negative');
  }

  function renderWarnings(warnings) {
    if (!warningsBox) return;
    if (!warnings || !warnings.length) {
      warningsBox.innerHTML = '';
      return;
    }
    warningsBox.innerHTML =
      '<div class="alert alert-warning py-2 fs-13 mb-0"><ul class="mb-0 ps-3">' +
      warnings.map((warning) => '<li>' + warning + '</li>').join('') +
      '</ul></div>';
  }

  function collectPayload() {
    return {
      year: document.getElementById('period-year').value,
      month: document.getElementById('period-month').value,
      entry_mode: entryMode.value,
      total_revenues: parseNumber('total-revenues'),
      cost_of_goods: parseNumber('cost-of-goods'),
      total_expenses: parseNumber('total-expenses'),
      other_income: parseNumber('other-income'),
      total_profit_loss: parseNumber('manual-total'),
    };
  }

  function renderPreview(data) {
    previewCard.classList.remove('d-none');
    previewError.classList.add('d-none');
    previewError.textContent = '';

    const preview = data.preview || {};
    const rows = preview.shareholders || [];
    previewBody.innerHTML = rows
      .map(
        (row) =>
          '<tr>' +
          '<td>' + row.name + '</td>' +
          '<td>' + row.ownership_percent.toFixed(2) + '%</td>' +
          '<td>' + currency(row.base_share) + '</td>' +
          '<td class="text-danger">' + currency(row.arrangement_deduction) + '</td>' +
          '<td class="text-success">' + currency(row.arrangement_received) + '</td>' +
          '<td class="text-end fw-semibold ' + (row.final_amount >= 0 ? 'text-success' : 'text-danger') + '">' +
          currency(row.final_amount) +
          '</td></tr>'
      )
      .join('');

    previewCompanyTotal.textContent = currency(preview.company_total);
    previewTypeBadge.textContent = preview.is_profit ? 'Profit' : 'Loss';
    previewTypeBadge.className =
      'badge ms-2 ' + (preview.is_profit ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger');
    previewReconcile.textContent =
      'Distributed ' + currency(preview.distributed_total) + ' · Variance ' + currency(preview.variance);

    if (data.warnings && data.warnings.length) {
      renderWarnings(data.warnings);
    }
  }

  async function previewDistribution() {
    if (!config.ownershipValid) {
      previewCard.classList.remove('d-none');
      previewError.classList.remove('d-none');
      previewError.textContent = 'Ownership must total 100% before previewing distribution.';
      previewBody.innerHTML = '';
      return;
    }

    previewBtn.disabled = true;
    previewBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Calculating...';

    try {
      const response = await fetch(config.previewUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': config.csrfToken,
        },
        body: JSON.stringify(collectPayload()),
      });
      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Could not preview distribution.');
      }
      renderPreview(data);
    } catch (error) {
      previewCard.classList.remove('d-none');
      previewError.classList.remove('d-none');
      previewError.textContent = error.message;
      previewBody.innerHTML = '';
    } finally {
      previewBtn.disabled = false;
      previewBtn.innerHTML = '<i class="mdi mdi-calculator"></i> Preview Distribution';
    }
  }

  if (entryMode) {
    entryMode.addEventListener('change', toggleEntryMode);
    toggleEntryMode();
  }

  document.querySelectorAll('.breakdown-input').forEach((input) => {
    input.addEventListener('input', updateComputedNet);
  });
  const manualTotal = document.getElementById('manual-total');
  if (manualTotal) manualTotal.addEventListener('input', updateComputedNet);

  if (previewBtn) previewBtn.addEventListener('click', previewDistribution);

  renderWarnings(config.warnings || []);
  updateComputedNet();
})();
