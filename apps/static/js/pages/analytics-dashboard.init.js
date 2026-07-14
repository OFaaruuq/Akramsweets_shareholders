/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: dashboard init Js
*/

// Earning Reports
const monthlySalesOptions = {
  series: [
    {
      name: "Income Growth",
      type: "line",
      data: [34, 65, 46, 68, 49, 61, 42, 44, 78, 52, 63, 67],
    },
    {
      name: "Expense Trend",
      type: "line",
      data: [16, 20, 32, 38, 42, 25, 15, 21, 17, 29, 12, 35],
    },
    {
      name: "Revenue",
      type: "bar",
      data: [12, 16, 28, 32, 38, 22, 10, 18, 14, 58, 24, 70],
    },
  ],
  chart: {
    height: 355,
    type: "line",
    toolbar: {
      show: false,
    },
  },
  stroke: {
    curve: "smooth",
    width: [3, 3, 0],
    dashArray: [0, 5, 0],
  },
  fill: {
    type: ["solid", "solid", "gradient"],
    gradient: {
      type: "vertical",
      shadeIntensity: 1,
      gradientToColors: ["#F39C12"],
      opacityFrom: 0.8,
      opacityTo: 0.3,
      stops: [0, 100],
    },
  },
  markers: {
    size: [5, 5, 0],
    hover: {
      size: 7,
    },
  },
  xaxis: {
    categories: [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ],
    axisTicks: {
      show: true,
    },
    axisBorder: {
      show: true,
    },
  },
  yaxis: {
    min: 0,
    labels: {
      formatter: function (value) {
        return value + "k";
      },
    },
    axisBorder: {
      show: false,
    },
  },
  grid: {
    show: true,
    strokeDashArray: 3,
    padding: {
      top: 10,
      left: 20,
      right: 20,
      bottom: 10,
    },
  },
  legend: {
    show: true,
    horizontalAlign: "center",
    offsetX: 0,
    offsetY: 5,
    markers: {
      width: 9,
      height: 9,
      radius: 6,
    },
    itemMargin: {
      horizontal: 10,
      vertical: 0,
    },
  },
  plotOptions: {
    bar: {
      columnWidth: "40%",
      borderRadius: 4,
    },
  },
  colors: ["#01D4FF", "#E7366B", "#46B277"], // Unique colors
  tooltip: {
    shared: true,
    intersect: false,
    y: {
      formatter: function (value) {
        return value.toFixed(1) + "k";
      },
    },
  },
};

const monthlySalesChart = new ApexCharts(document.querySelector("#monthly-sales"), monthlySalesOptions);
monthlySalesChart.render();


// Database Items
const saleGrowthOptions = {
  series: [
    {
      name: 'Last Year',
      data: [24, 22, 20, 26, 28, 35, 28, 23, 28, 34, 30, 34,]
    },
    {
      name: 'This Year',
      data: [30, 25, 30, 36, 32, 36, 36, 34, 39, 42, 33, 37,]
    }
  ],
  chart: {
    type: 'area',
    height: 359,
    stacked: true,
    toolbar: {
      show: false
    }
  },
  colors: ['#7E57C2', '#42A5F5'],
  dataLabels: {
    enabled: false,
  },
  stroke: {
    width: [2, 2],
    curve: 'straight',
    lineCap: 'butt',
  },
  fill: {
    type: 'gradient',
    gradient: {
      opacityFrom: 0.6,
      opacityTo: 0.8,
    }
  },
  grid: {
    show: true,
    strokeDashArray: 3,
    xaxis: {
      lines: {
        show: false,
      },
    },
    yaxis: {
      lines: {
        show: true,
      },
    },
    padding: {
      top: 0,
      right: -2,
      bottom: 0,
      left: 10,
    },
  },
  xaxis: {
    type: 'month',
    categories: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'sep', 'oct', 'nov', 'dec'],
    axisTicks: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
  },
  yaxis: {
    min: 0,
    axisBorder: {
      show: false,
    },
  },
  legend: {
    show: true,
    horizontalAlign: "center",
    offsetX: 0,
    offsetY: 5,
    markers: {
      width: 9,
      height: 9,
      radius: 6,
    },
    itemMargin: {
      horizontal: 10,
      vertical: 0,
    },
  },
  tooltip: {
    shared: true,
    y: [
      {
        formatter: function (y) {
          if (typeof y !== "undefined") {
            return y.toFixed(1) + "k";
          }
          return y;
        },
      },
      {
        formatter: function (y) {
          if (typeof y !== "undefined") {
            return y.toFixed(1) + "k";
          }
          return y;
        },
      }
    ],
  },
};

const saleGrowthChart = new ApexCharts(document.querySelector("#salegrowthrate"), saleGrowthOptions);
saleGrowthChart.render();


// Top Session
const topSessionOptions = {
  series: [65.48, 112.02, 80.48, 58.65],
  labels: ["Chrome", "Firefox", "Safari", "Opera"],
  chart: {
    type: "donut",
    height: 270,
  },
  plotOptions: {
    pie: {
      size: 100,
      donut: {
        size: "80%",
      },
    },
  },
  dataLabels: {
    enabled: false,
  },
  legend: {
    show: false,
  },
  stroke: {
    width: 0,
  },
  yaxis: {
    labels: {
      formatter: function (e) {
        return e + "k Session";
      },
    },
    tickAmount: 4,
    min: 0,
  },
  colors: ["#46B277", "#522c8f", "#E77636", "#01D4FF"],
};

const topSessionChart = new ApexCharts(document.querySelector("#device-views"), topSessionOptions);
topSessionChart.render();