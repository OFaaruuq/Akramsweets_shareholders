/*
Monthly Mudarabah profit distribution — Net Profit from Odoo drives the split
*/

(function () {
  const config = window.AKRAM_PERIOD_FORM || {};
  const form = document.getElementById('period-create-form');
  if (!form) return;

  const previewBtn = document.getElementById('preview-distribution-btn');
  const previewCard = document.getElementById('preview-card');
  const previewBody = document.getElementById('preview-table-body');
  const previewCompanyTotal = document.getElementById('preview-company-total');
  const previewCompanyNet = document.getElementById('preview-company-net');
  const previewPool = document.getElementById('preview-pool');
  const previewPartner = document.getElementById('preview-partner');
  const previewDistributed = document.getElementById('preview-distributed');
  const previewRemaining = document.getElementById('preview-remaining');
  const previewPoolPct = document.getElementById('preview-pool-pct');
  const previewPartnerPct = document.getElementById('preview-partner-pct');
  const previewFormulaText = document.getElementById('preview-formula-text');
  const previewTypeBadge = document.getElementById('preview-type-badge');
  const previewReconcile = document.getElementById('preview-reconcile');
  const previewError = document.getElementById('preview-error');
  const warningsBox = document.getElementById('period-warnings');
  const netInput = document.getElementById('pnl-net-profit');

  const mudarabahPct = Number(config.mudarabahPercent);
  const partnerPct = Number(
    config.partnerPercent != null ? config.partnerPercent : 100 - (Number.isFinite(mudarabahPct) ? mudarabahPct : 50)
  );
  const partnerName = config.partnerName || 'Managing Partner';
  const safeMudarabahPct = Number.isFinite(mudarabahPct) ? mudarabahPct : 50;
  const safePartnerPct = Number.isFinite(partnerPct) ? partnerPct : 100 - safeMudarabahPct;

  const currencySymbol = config.currencySymbol || window.AKRAM_CURRENCY_SYMBOL || '$';
  const currency = (value) => {
    const amount = Number(value) || 0;
    const formatted = Math.abs(amount).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return (amount < 0 ? '-' : '') + currencySymbol + formatted;
  };

  const parseNumber = (id) => {
    const el = document.getElementById(id);
    if (!el) return 0;
    const value = parseFloat(el.value);
    return Number.isFinite(value) ? value : 0;
  };

  function updateLiveFormula() {
    const net = parseNumber('pnl-net-profit');
    const pool = (net * safeMudarabahPct) / 100;
    const partner = net - pool;
    const set = (id, value) => {
      const el = document.getElementById(id);
      if (el) el.textContent = typeof value === 'string' ? value : currency(value);
    };
    set('formula-net', net);
    set('formula-pool', pool);
    set('formula-partner', partner);
    set('formula-distributed', pool);
    set('formula-remaining', 0);
    const poolPctEl = document.getElementById('formula-pool-pct');
    const partnerPctEl = document.getElementById('formula-partner-pct');
    const partnerNameEl = document.getElementById('formula-partner-name');
    if (poolPctEl) poolPctEl.textContent = String(safeMudarabahPct);
    if (partnerPctEl) partnerPctEl.textContent = String(safePartnerPct);
    if (partnerNameEl) partnerNameEl.textContent = partnerName;
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
      total_profit_loss: parseNumber('pnl-net-profit'),
      income: parseNumber('pnl-income'),
      gross_profit: parseNumber('pnl-gross-profit'),
      total_gross_profit: parseNumber('pnl-total-gross-profit'),
      total_income: parseNumber('pnl-total-income'),
      total_expenses: parseNumber('pnl-total-expenses'),
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
          '<td class="text-end">' + currency(row.investment) + '</td>' +
          '<td class="text-end">' + (row.shares ? Number(row.shares).toFixed(4) : '—') + '</td>' +
          '<td class="text-end">' + Number(row.ownership_percent).toFixed(4) + '%</td>' +
          '<td class="text-end">' + currency(row.original_profit != null ? row.original_profit : row.base_share) + '</td>' +
          '<td class="text-end">' + currency(row.arrangement_adjustment != null ? row.arrangement_adjustment : ((row.arrangement_deduction || 0) + (row.arrangement_received || 0))) + '</td>' +
          '<td class="text-end fw-semibold ' + ((row.profit != null ? row.profit : row.final_amount) >= 0 ? 'text-success' : 'text-danger') + '">' +
          currency(row.profit != null ? row.profit : row.final_amount) +
          '</td></tr>'
      )
      .join('');

    const pool = preview.shareholders_pool != null ? preview.shareholders_pool : preview.distributed_total;
    previewCompanyTotal.textContent = currency(pool);
    if (previewCompanyNet) previewCompanyNet.textContent = currency(preview.company_total);
    if (previewPool) previewPool.textContent = currency(preview.shareholders_pool);
    if (previewPartner) previewPartner.textContent = currency(preview.managing_partner_share);
    if (previewDistributed) previewDistributed.textContent = currency(preview.distributed_total);
    if (previewRemaining) previewRemaining.textContent = currency(preview.remaining_balance != null ? preview.remaining_balance : preview.variance);
    if (previewPoolPct && preview.mudarabah_shareholder_percent != null) {
      previewPoolPct.textContent = '(' + Number(preview.mudarabah_shareholder_percent).toFixed(0) + '%)';
    }
    if (previewPartnerPct) {
      const pct = preview.mudarabah_partner_percent != null
        ? preview.mudarabah_partner_percent
        : safePartnerPct;
      previewPartnerPct.textContent = '(' + Number(pct).toFixed(0) + '%)';
    }
    if (previewFormulaText && preview.formula) {
      const f = preview.formula;
      previewFormulaText.textContent =
        'Net Profit = ' + currency(f.net_profit) +
        '  →  Shareholders Pool (' + Number(f.shareholder_percent).toFixed(0) + '%) = ' + currency(f.shareholders_pool) +
        '  →  ' + partnerName + ' (' + Number(f.partner_percent).toFixed(0) + '%) = ' + currency(f.akram_share);
    }
    previewTypeBadge.textContent = preview.is_profit ? 'Profit' : 'Loss';
    previewTypeBadge.className =
      'badge ms-2 ' + (preview.is_profit ? 'bg-success-subtle text-success' : 'bg-danger-subtle text-danger');
    previewReconcile.textContent =
      'Pool distributed ' + currency(preview.distributed_total) + ' · Remaining ' + currency(preview.remaining_balance != null ? preview.remaining_balance : preview.variance);

    if (data.warnings && data.warnings.length) {
      renderWarnings(data.warnings);
    }
  }

  async function previewDistribution() {
    if (!config.ownershipValid) {
      previewCard.classList.remove('d-none');
      previewError.classList.remove('d-none');
      previewError.textContent = 'Ownership must total exactly 100.0000% before previewing distribution.';
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
      if (data.ownership_valid === false) {
        throw new Error('Ownership must total exactly 100.0000% before previewing distribution.');
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

  const unlockPnl = document.getElementById('unlock-pnl-ref');
  if (unlockPnl) {
    unlockPnl.addEventListener('change', function () {
      document.querySelectorAll('#odoo-pnl-ref .pnl-input').forEach(function (el) {
        el.readOnly = !unlockPnl.checked;
      });
    });
  }

  if (previewBtn) previewBtn.addEventListener('click', previewDistribution);
  if (netInput) {
    netInput.addEventListener('input', updateLiveFormula);
    netInput.addEventListener('change', updateLiveFormula);
  }
  updateLiveFormula();
  renderWarnings(config.warnings || []);
})();
