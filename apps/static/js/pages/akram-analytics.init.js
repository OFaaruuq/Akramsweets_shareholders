/*
Akram Sweets Shareholders Analytics charts
*/

(function () {
  const data = window.AKRAM_ANALYTICS || {};
  const analytics = data.analytics || {};
  const earning = analytics.earning_reports || { labels: [], profits: [], distributed: [], expenses: [], revenues: [] };
  const growth = analytics.growth_rate || { labels: [], company: [], distributed: [] };
  const distributionPie = data.distribution_pie || { labels: ['No data'], series: [1] };
  const shareholderSeries = analytics.shareholder_series || { labels: [], series: [] };
  const isShareholderView = !!analytics.is_shareholder_view;

  const currency = (value) => '$' + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const palette = ['#8A1B24', '#C8924B', '#46B277', '#01D4FF', '#E77636', '#E7366B', '#522c8f'];

  function renderChart(selector, options) {
    const el = document.querySelector(selector);
    if (!el) return;
    new ApexCharts(el, options).render();
  }

  const earningSeries = [
    { name: isShareholderView ? 'My Payout' : 'Company P/L', type: 'line', data: earning.profits || [0] },
    { name: isShareholderView ? 'Cumulative View' : 'Distributed', type: 'line', data: earning.distributed || [0] },
  ];
  if (!isShareholderView) {
    earningSeries.push({ name: 'Total Revenues', type: 'bar', data: earning.revenues || [0] });
    earningSeries.push({ name: 'Total Expenses', type: 'bar', data: earning.expenses || [0] });
  }

  renderChart('#monthly-sales', {
    series: earningSeries,
    chart: { height: 355, type: 'line', toolbar: { show: true, tools: { download: true, selection: false, zoom: true, zoomin: true, zoomout: true, pan: false, reset: true } } },
    stroke: { curve: 'smooth', width: earningSeries.map((_, index) => (index < 2 ? 3 : 0)), dashArray: [0, 6, 0, 0] },
    fill: {
      type: earningSeries.map((_, index) => (index >= 2 ? 'gradient' : 'solid')),
      gradient: { type: 'vertical', shadeIntensity: 1, opacityFrom: 0.75, opacityTo: 0.25, stops: [0, 100] },
    },
    markers: { size: earningSeries.map((_, index) => (index < 2 ? 4 : 0)), hover: { size: 6 } },
    xaxis: { categories: earning.labels || ['N/A'], axisTicks: { show: true }, axisBorder: { show: true } },
    yaxis: {
      labels: {
        formatter: function (value) {
          if (Math.abs(value) >= 1000) return '$' + (value / 1000).toFixed(1) + 'K';
          return '$' + value.toFixed(0);
        },
      },
    },
    grid: { show: true, strokeDashArray: 3 },
    legend: { show: true, horizontalAlign: 'center' },
    plotOptions: { bar: { columnWidth: '35%', borderRadius: 4 } },
    colors: ['#8A1B24', '#C8924B', '#46B277', '#E7366B'],
    tooltip: { shared: true, y: { formatter: currency } },
  });

  renderChart('#salegrowthrate', {
    series: [
      { name: isShareholderView ? 'My Payout' : 'Company P/L', data: growth.company || [0] },
      { name: isShareholderView ? 'Trend' : 'Distributed', data: growth.distributed || [0] },
    ],
    chart: { type: 'area', height: 359, toolbar: { show: false } },
    colors: ['#8A1B24', '#C8924B'],
    dataLabels: { enabled: false },
    stroke: { width: [2, 2], curve: 'smooth' },
    fill: { type: 'gradient', gradient: { opacityFrom: 0.55, opacityTo: 0.15 } },
    grid: { show: true, strokeDashArray: 3 },
    xaxis: { categories: growth.labels || ['N/A'], axisTicks: { show: false }, axisBorder: { show: false } },
    yaxis: { labels: { formatter: currency } },
    legend: { show: true, horizontalAlign: 'center' },
    tooltip: { shared: true, y: { formatter: currency } },
  });

  if (shareholderSeries.series && shareholderSeries.series.length) {
    renderChart('#shareholder-breakdown', {
      series: shareholderSeries.series,
      chart: { type: 'bar', height: 320, stacked: true, toolbar: { show: false } },
      plotOptions: { bar: { horizontal: false, columnWidth: '55%', borderRadius: 3 } },
      xaxis: { categories: shareholderSeries.labels || ['N/A'] },
      yaxis: { labels: { formatter: currency } },
      legend: { position: 'top', horizontalAlign: 'center' },
      colors: palette,
      dataLabels: { enabled: false },
      tooltip: { shared: true, intersect: false, y: { formatter: currency } },
      grid: { strokeDashArray: 3 },
    });
  }

  renderChart('#device-views', {
    series: distributionPie.series || [1],
    labels: distributionPie.labels || ['No data'],
    chart: { type: 'donut', height: 270 },
    plotOptions: { pie: { donut: { size: '78%', labels: { show: true, total: { show: true, label: 'Total', formatter: () => currency(distributionPie.series.reduce((a, b) => a + b, 0)) } } } } },
    dataLabels: { enabled: true, formatter: (value) => value.toFixed(1) + '%' },
    legend: { show: false },
    stroke: { width: 0 },
    colors: palette,
    tooltip: { y: { formatter: currency } },
  });
})();
