/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Apexcharts Radar Charts
*/

//
// Basic Radar Chart
//

const basicRadarOptions = {
  series: [
    {
      name: "Series 1",
      data: [80, 50, 30, 40, 100, 20],
    },
  ],
  chart: {
    height: 350,
    type: "radar",
    parentHeightOffset: 0,
  },
  title: {
    text: "Basic Radar Chart",
  },
  colors: ["#7168EE"],
  yaxis: {
    stepSize: 20,
  },
  xaxis: {
    categories: ["January", "February", "March", "April", "May", "June"],
  },
};
const basicRadarChart = new ApexCharts(document.querySelector("#basic_radar_chart"), basicRadarOptions);
basicRadarChart.render();

//
// Multiple Series Radar Chart
//
const multipleRadarOptions = {
  series: [
    {
      name: "Series 1",
      data: [80, 50, 30, 40, 100, 20],
    },
    {
      name: "Series 2",
      data: [20, 30, 40, 80, 20, 80],
    },
    {
      name: "Series 3",
      data: [44, 76, 78, 13, 43, 10],
    },
  ],
  chart: {
    height: 350,
    type: "radar",
    parentHeightOffset: 0,
    dropShadow: {
      enabled: true,
      blur: 1,
      left: 1,
      top: 1,
    },
  },
  colors: ["#7168EE", "#E7366B", "#E77636"],
  title: {
    text: "Radar Chart - Multi Series",
  },
  stroke: {
    width: 2,
  },
  fill: {
    opacity: 0.1,
  },
  markers: {
    size: 0,
  },
  yaxis: {
    stepSize: 20,
  },
  xaxis: {
    categories: ["2011", "2012", "2013", "2014", "2015", "2016"],
  },
};
const multipleRadarChart = new ApexCharts(document.querySelector("#multiple_radar_chart"), multipleRadarOptions);
multipleRadarChart.render();

//
// Polygon Fill Radar Chart
//
const polygonFillRadarOptions = {
  series: [
    {
      name: "Series 1",
      data: [20, 100, 40, 30, 50, 80, 33],
    },
  ],
  chart: {
    height: 350,
    type: "radar",
    parentHeightOffset: 0,
  },
  dataLabels: {
    enabled: true,
  },
  plotOptions: {
    radar: {
      size: 140,
    },
  },
  title: {
    text: "Radar with Polygon Fill",
  },
  colors: ["#46B277"],
  markers: {
    size: 4,
    colors: ["#fff"],
    strokeColor: "#46B277",
    strokeWidth: 2,
  },
  tooltip: {
    y: {
      formatter: function (val) {
        return val;
      },
    },
  },
  xaxis: {
    categories: [
      "Sunday",
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
    ],
  },
  yaxis: {
    labels: {
      formatter: function (val, i) {
        if (i % 2 === 0) {
          return val;
        } else {
          return "";
        }
      },
    },
  },
};
const polygonFillRadarChart = new ApexCharts(document.querySelector("#polygonfill_radar_chart"), polygonFillRadarOptions);
polygonFillRadarChart.render();
