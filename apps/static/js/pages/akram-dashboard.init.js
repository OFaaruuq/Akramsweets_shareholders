/*
Akram Sweets Shareholders Dashboard charts
*/

(function () {
  const data = window.AKRAM_DASHBOARD || {};
  const sparklines = data.sparklines || {};
  const profitOverTime = data.profit_over_time || { labels: [], profits: [], distributed: [] };
  const distributionPie = data.distribution_pie || { labels: ['No data'], series: [1], rows: [] };
  const revenueStats = data.revenue_stats || { labels: [], profits: [], revenues: [] };

  function sparklineOptions(values, color) {
    return {
      series: [{ name: 'Value', data: values.length ? values : [0] }],
      chart: {
        height: 45,
        type: 'area',
        sparkline: { enabled: true },
        animations: { enabled: false },
        dropShadow: {
          enabled: true,
          top: 10,
          left: 0,
          bottom: 10,
          blur: 2,
          color: '#f0f4f7',
          opacity: 0.3,
        },
      },
      colors: [color],
      fill: {
        type: 'gradient',
        gradient: { shadeIntensity: 1, opacityFrom: 0.5, opacityTo: 0.5, stops: [0, 90, 100] },
      },
      tooltip: { enabled: false },
      dataLabels: { enabled: false },
      grid: { show: false },
      xaxis: { labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: { show: false },
      stroke: { curve: 'smooth', width: 1 },
    };
  }

  function renderChart(selector, options) {
    const el = document.querySelector(selector);
    if (!el) return;
    const chart = new ApexCharts(el, options);
    chart.render();
  }

  renderChart('#total_sales', sparklineOptions(sparklines.revenues || [], '#8A1B24'));
  renderChart('#total_orders', sparklineOptions(sparklines.profit || [], '#46B277'));
  renderChart('#new_customers', sparklineOptions(sparklines.shareholders || [], '#C8924B'));
  renderChart('#total_income', sparklineOptions(sparklines.distributed || [], '#8A1B24'));
  renderChart('#total_returns', sparklineOptions(sparklines.pending || [], '#E77636'));

  renderChart('#categories_chart', {
    series: distributionPie.series || [1],
    labels: distributionPie.labels || ['No data'],
    chart: { type: 'donut', height: 385 },
    plotOptions: {
      pie: {
        startAngle: -90,
        endAngle: 90,
        offsetY: 10,
        donut: { size: '70%' },
      },
    },
    stroke: { borderRadius: 15, width: 4, colors: ['#fff'] },
    dataLabels: { enabled: false },
    grid: { padding: { bottom: -190 } },
    colors: ['#8A1B24', '#46B277', '#C8924B', '#01D4FF', '#E77636', '#E7366B'],
    legend: { show: false },
  });

  const maxY = Math.max(
    1,
    ...(profitOverTime.profits || []),
    ...(profitOverTime.distributed || [])
  );

  renderChart('#sales-overtime', {
    series: [
      { name: 'Company P/L', data: profitOverTime.profits || [0] },
      { name: 'Distributed', data: profitOverTime.distributed || [0] },
    ],
    chart: { type: 'area', height: 290, toolbar: { show: false } },
    colors: ['#8A1B24', '#C8924B'],
    dataLabels: { enabled: false },
    stroke: { curve: 'smooth', width: 2 },
    fill: {
      type: 'gradient',
      gradient: { shadeIntensity: 1, opacityFrom: 0.7, opacityTo: 0.2, stops: [0, 90, 100] },
    },
    xaxis: {
      categories: profitOverTime.labels || ['N/A'],
      axisBorder: { show: false },
      axisTicks: { show: false },
      labels: { style: { colors: '#9aa0ac' } },
    },
    yaxis: {
      labels: {
        formatter: function (val) {
          if (Math.abs(val) >= 1000) return '$' + (val / 1000).toFixed(1) + 'K';
          return '$' + val.toFixed(0);
        },
        style: { colors: '#9aa0ac' },
      },
      min: Math.min(0, ...(profitOverTime.profits || [0])),
      max: maxY * 1.1,
      tickAmount: 4,
    },
    tooltip: {
      shared: true,
      intersect: false,
      y: { formatter: (value) => '$' + Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 }) },
    },
    legend: { position: 'top', horizontalAlign: 'right' },
    grid: { borderColor: '#f1f1f1', strokeDashArray: 3 },
  });

  renderChart('#revenueCharts', {
    series: [
      { name: 'Monthly P/L', type: 'column', data: revenueStats.profits || [0] },
      { name: 'Total Revenues', type: 'column', data: revenueStats.revenues || [0] },
    ],
    chart: { type: 'bar', height: 200, toolbar: { show: false } },
    grid: { borderColor: '#f1f1f1', strokeDashArray: 3 },
    colors: ['#8A1B24', '#C8924B'],
    plotOptions: { bar: { borderRadius: 1, horizontal: false, columnWidth: '50%' } },
    dataLabels: { enabled: false },
    legend: { show: false },
    stroke: { show: true, width: 4, colors: ['transparent'] },
    xaxis: {
      categories: revenueStats.labels || ['N/A'],
      axisBorder: { show: true, color: 'rgba(167, 180, 201 ,0.2)' },
    },
  });
})();
