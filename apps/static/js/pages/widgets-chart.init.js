/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Widgets Js
*/

// Employee Performance Rating Chart
const chartEmployeePerformanceOptions = {
    series: [{
        name: 'Task completed',
        data: [44, 55, 41, 37, 44]
    }, {
        name: 'Presence',
        data: [53, 32, 33, 52, 22]
    }, {
        name: 'Completed Meeting',
        data: [12, 24, 22, 23, 35]
    }],
    chart: {
        type: 'bar',
        height: 355,
        stacked: true,
        parentHeightOffset: 0,
        toolbar: {
            show: false
        },
        zoom: {
            enabled: true
        }
    },
    plotOptions: {
        bar: {
            horizontal: true,
            barHeight: '50%',
            dataLabels: {
                show: false,
                total: {
                    enabled: false,
                }
            }
        },
    },
    stroke: {
        width: 1,
        colors: ['#fff']
    },
    xaxis: {
        categories: ["Hazel Nutt", "Simon Cyrence", "Aida bugga", "Peg Legge", "Barb Akew"],
        labels: {
            formatter: function (val) {
                return val
            }
        }
    },
    yaxis: {
        title: {
            text: undefined
        },
        labels: {
            style: {
                fontSize: '13px',
                fontFamily: 'Public Sans", sans-serif',
                fontWeight: 500,
                cssClass: 'apexcharts-yaxis-label',
            },
        },

    },
    tooltip: {
        y: {
            formatter: function (val) {
                return val
            }
        }
    },

    colors: ["rgba(231, 118, 54, 0.8)", "rgba(231, 118, 54, 0.5)", "rgba(231, 118, 54, 0.2)"],
    fill: {
        opacity: 1
    },
    legend: {
        position: 'bottom',
        horizontalAlign: 'center',
        show: true,
    },
    grid: {
        padding: {
            top: -20,
            right: 0,
            bottom: 0
        },
        strokeDashArray: 4,
        xaxis: {
            lines: {
                show: true
            }
        },
    },
};

const chartEmployeePerformanceChart = new ApexCharts(document.querySelector("#employeeRating-chart"), chartEmployeePerformanceOptions);
chartEmployeePerformanceChart.render();

//  Money Flow Chart
const moneyFlowOptions = {
    chart: {
        type: 'bar',
        height: 345,
        stacked: true,
        parentHeightOffset: 0,
        toolbar: {
            show: false
        },
        zoom: {
            enabled: true
        }
    },
    series: [{
        name: 'Profit',
        data: [300, 333, 258, 295, 258, 326, 275, 283, 271, 316, 334, 271]
    }, {
        name: 'Income',
        data: [300, 333, 258, 295, 258, 326, 275, 283, 271, 316, 333, 271]
    }, {
        name: 'Expense',
        data: [300, 333, 258, 295, 259, 326, 275, 283, 271, 316, 333, 271]
    }],
    plotOptions: {
        bar: {
            horizontal: false,
            borderRadius: 5,
            borderRadiusApplication: 'end', // 'around', 'end'
            borderRadiusWhenStacked: 'last', // 'all', 'last'
            columnWidth: '60%',
            dataLabels: {
                total: {
                    style: {
                        fontSize: '13px',
                        fontWeight: 900,
                    }
                }
            },
        },
    },
    dataLabels: {
        enabled: false,
    },
    xaxis: {
        categories: ['Jan', 'Fab', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
        axisBorder: {
            show: false,
        },
    },
    yaxis: {
        labels: {
            padding: 4
        },
    },
    colors: ["rgba(113, 104, 238, 0.8)", "rgba(113, 104, 238, 0.5)", "rgba(113, 104, 238, 0.2)"],
    legend: {
        position: 'top',
        show: true,
        horizontalAlign: 'right'
    },
    fill: {
        opacity: 1
    },
    grid: {
        padding: {
            top: -20,
            right: 0,
            bottom: 0
        },
        strokeDashArray: 4,
        xaxis: {
            lines: {
                show: true
            }
        },
    },
};
const moneyFlowChart = new ApexCharts(document.querySelector("#chart-money"), moneyFlowOptions);
moneyFlowChart.render();


// Traffic 
const trafficOptions = {
    series: [
        {
            name: "Marketing",
            data: [8, 12, 8, 9, 12, 14, 15, 18, 15, 19, 20, 25, 15, 17, 18, 7, 13, 15, 20, 2, 22, 21, 25, 30, 24, 27, 32, 28, 35, 31, 26, 40, 29, 33, 37, 34, 39]
        },
        {
            name: "Developing",
            data: [8, 9, 10, 8, 12, 10, 12, 11, 15, 18, 19, 15, 18, 21, 17, 9, 20, 22, 19, 11, 23, 21, 24, 27, 25, 28, 30, 26, 29, 31, 33, 35, 32, 34, 36, 37, 38]
        },
        {
            name: "Other",
            data: [13, 19, 13, 11, 10, 11, 13, 14, 15, 18, 16, 20, 17, 20, 19, 11, 22, 24, 21, 13, 26, 25, 28, 29, 27, 30, 32, 31, 34, 33, 35, 36, 38, 37, 40, 39, 41]
        }
    ],
    chart: {
        type: 'bar',
        height: 200,
        parentHeightOffset: 0,
        zoom: {
            enabled: false
        },
        toolbar: {
            show: false
        },
        animations: {
            enabled: false
        },
        stacked: true,
    },
    plotOptions: {
        bar: {
            columnWidth: '50%',
        }
    },
    dataLabels: {
        enabled: false,
    },
    fill: {
        opacity: 1,
    },
    grid: {
        padding: {
            top: -20,
            right: 0,
            bottom: 10
        },
        strokeDashArray: 4,
        xaxis: {
            lines: {
                show: true
            }
        },
    },
    xaxis: {
        labels: {
            padding: 0,
        },
        tooltip: {
            enabled: false
        },
        axisBorder: {
            show: false,
        },
        type: 'datetime',
    },
    yaxis: {
        labels: {
            padding: 4
        },
    },
    labels: [
        '2021-01-01', '2021-01-02', '2021-01-03', '2021-01-04', '2021-01-05', '2021-01-06', '2021-01-07', '2021-01-08', '2021-01-09', '2021-01-10', '2021-01-11', '2021-01-12', '2021-01-13', '2021-01-14', '2021-01-15', '2021-01-16', '2021-01-17', '2021-01-18', '2021-01-19', '2021-01-20', '2021-01-21', '2021-01-22', '2021-01-23', '2021-01-24', '2021-01-25', '2021-01-26', '2021-01-27', '2021-01-28', '2021-01-29', '2021-01-30', '2021-01-31', '2021-02-01', '2021-02-02', '2021-02-03', '2021-02-04', '2021-02-05', '2021-02-06'
    ],
    colors: ["#135046", "#73bbe2", "#46B277"],
    legend: {
        show: false,
    },
};
const trafficChart = new ApexCharts(document.querySelector("#chart-traffic"), trafficOptions);
trafficChart.render();

//  Subscribers data
const subscribersOptions = {
    chart: {
        type: 'area',
        height: 140,
        parentHeightOffset: 0,
        sparkline: {
            enabled: true
        },
        animations: {
            enabled: false
        },
        stacked: true,
    },
    dataLabels: {
        enabled: false,
    },
    colors: ["#46B277"],
    fill: {
        type: "gradient",
        gradient: {
            shadeIntensity: 0.5,
            gradientToColors: ["#7168EE", "#fa709a"], // Gradient end colors for lines
            inverseColors: false,
            opacityFrom: 0.9,
            opacityTo: 0.4,
            stops: [0, 90, 100]
        },
    },
    stroke: {
        width: 2,
        lineCap: "round",
        curve: "smooth",
    },
    series: [
        {
            name: "Purchases",
            data: [15, 20, 25, 27, 21, 25, 27, 29, 24, 35, 30, 40, 34, 25, 29, 30, 32, 34, 39, 28, 26, 35, 39, 32, 40, 55, 60, 48, 52, 70]
        }
    ],
    plotOptions: {
        bar: {
            columnWidth: '50%',
        }
    },
    grid: {
        padding: {
            top: -20,
            right: 0,
            bottom: 10
        },
        strokeDashArray: 4,
        xaxis: {
            lines: {
                show: true
            }
        },
    },
    xaxis: {
        labels: {
            padding: 0,
        },
        tooltip: {
            enabled: false
        },
        axisBorder: {
            show: false,
        },
        type: 'datetime',
        tickAmount: 6,
    },
    yaxis: {
        labels: {
            padding: 4
        },
    },
    labels: [
        '2020-06-21', '2020-06-22', '2020-06-23', '2020-06-24', '2020-06-25', '2020-06-26', '2020-06-27', '2020-06-28', '2020-06-29', '2020-06-30', '2020-07-01', '2020-07-02', '2020-07-03', '2020-07-04', '2020-07-05', '2020-07-06', '2020-07-07', '2020-07-08', '2020-07-09', '2020-07-10', '2020-07-11', '2020-07-12', '2020-07-13', '2020-07-14', '2020-07-15', '2020-07-16', '2020-07-17', '2020-07-18', '2020-07-19', '2020-07-20'
    ],
    legend: {
        show: false,
    },
    point: {
        show: false
    }
};
const subscribersChart = new ApexCharts(document.querySelector("#chart-development-activity"), subscribersOptions);
subscribersChart.render();


// Web Analytics
const webAnalyticsOptions = {
    series: [
        {
            name: "Last 9 days",
            data: [85, 80, 150, 127, 220, 200, 300, 290, 314]
        },
        {
            name: "Preceding period",
            data: [215, 165, 100, 200, 145, 185, 104, 124, 82]
        }
    ],
    chart: {
        type: 'line',
        height: 240,
        parentHeightOffset: 0,
        zoom: {
            enabled: false
        },
        toolbar: {
            show: false
        },
        animations: {
            enabled: false
        },
    },
    dataLabels: {
        enabled: false
    },
    colors: ["#46B277", "#f59440"],
    fill: {
        type: "gradient",
    },
    stroke: {
        width: [2, 2],
        curve: 'straight',
        dashArray: [0, 7]
    },
    legend: {
        position: 'bottom',
        horizontalAlign: 'left',
        tooltipHoverFormatter: function (val, opts) {
            return val + ' <strong>' + opts.w.globals.series[opts.seriesIndex][opts.dataPointIndex] + '</strong>'
        }
    },
    markers: {
        size: 0,
        hover: {
            sizeOffset: 6
        }
    },
    grid: {
        padding: {
            top: -20,
            right: 0,
            bottom: 10
        },
        strokeDashArray: 4,
        xaxis: {
            lines: {
                show: true
            }
        },
    },
    xaxis: {
        labels: {
            padding: 0,
        },
        axisBorder: {
            show: false,
        },
        tooltip: {
            enabled: false
        },
        categories: ['09', '10', '11', '12', '13', '14', '15', '16'],
    },
    tooltip: {
        y: [
            {
                title: {
                    formatter: function (val) {
                        return val
                    }
                }
            },
            {
                title: {
                    formatter: function (val) {
                        return val
                    }
                }
            }
        ]
    }
};
const webAnalyticsChart = new ApexCharts(document.querySelector("#chart-new-clients"), webAnalyticsOptions);
webAnalyticsChart.render();

// Website Visitors
const websiteVisitorsOptions = {
    series: [{
        name: 'Website Visitor',
        data: [44, 55, 57, 56, 61, 58, 63, 60, 66]
    }],
    chart: {
        height: 352,
        type: 'bar',
        parentHeightOffset: 0,
        toolbar: {
            show: false
        },
    },
    plotOptions: {
        bar: {
            horizontal: false,
            columnWidth: '35%',
            endingShape: 'rounded',
            borderRadius: 5,
            borderRadiusApplication: 'end', // 'around', 'end'
            borderRadiusWhenStacked: 'last', // 'all', 'last'
        },
    },
    dataLabels: {
        enabled: false
    },
    colors: ["#f59440"],
    stroke: {
        curve: 'smooth',
        lineCap: 'round',
        width: '1',
        dashArray: 0,
    },
    xaxis: {
        categories: ['Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct'],
    },
    fill: {
        opacity: 1
    },
    tooltip: {
        y: {
            formatter: function (val) {
                return val + " K"
            }
        }
    },
    grid: {
        strokeDashArray: 4,
    },
};
const websiteVisitorsChart = new ApexCharts(document.querySelector("#website-visitors"), websiteVisitorsOptions);
websiteVisitorsChart.render();

// Orders Overview
const ordersOverviewOptions = {
    series: [88, 85, 75, 60],
    labels: ["Delivered", "Returned", "Cancelled", "Pending"],
    chart: {
        height: 313,
        type: 'radialBar',
    },
    dataLabels: {
        enabled: false,
    },
    legend: {
        show: false,
    },
    stroke: {
        show: true,
        curve: 'smooth',
        lineCap: 'round',
        colors: "#fff",
        width: 0,
        dashArray: 0,
    },
    plotOptions: {
        radialBar: {
          dataLabels: {
            name: {
                offsetY: -3,
                show: true,
                color: 'var(--text-muted)',
                fontSize: '14px',
                fontWeight: '400'
            },
            value: {
                color: '#111',
                fontSize: '14px',
                offsetY: 2,
                show: true,
            },
            total: {
              show: true,
              label: 'Total',
              color: 'var(--text-muted)',
              formatter: function (w) {
                return 380
              }
            }
          }
        }
      },
    colors: ["#7168EE", "rgba(82, 44, 143, 0.8)", "rgba(231, 54, 107, 0.8)", "rgba(231, 118, 54, 0.8)"],
};
const ordersOverviewChart = new ApexCharts(document.querySelector("#recent-orders"), ordersOverviewOptions);
ordersOverviewChart.render();


// Average Revenue
const averageRevenueOptions = {
    series: [{
        name: "Revenue chart",
        data: [12500, 8000, 7800, 9000, 6200, 6000, 4700, 4700, 5200, 5000, 5700, 5500, 5800, 5500, 6200, 5500, 5500, 2400, 2600, 2000]
    }],
    chart: {
        type: 'area',
        height: 250,
        parentHeightOffset: 0,
        zoom: {
            enabled: false
        },
        toolbar: {
            show: false
        },
    },
    dataLabels: {
        enabled: false
    },
    stroke: {
        curve: 'smooth',
        lineCap: 'round',
        width: '1',
        dashArray: 0,
    },
    xaxis: {
        categories: ['22 May', '23 May', '24 May', '25 May', '26 May', '27 May', '28 May', '29 May', '30 May', '01 June', '02 June', '03 June', '04 June', '05 June', '06 June', '07 June', '08 June', '09 June', '10 June'],
    },
    legend: {
        position: 'top',
        show: true,
        horizontalAlign: 'right'
    },
    fill: {
        opacity: 1
    },
    colors: ["#46B277"],
    grid: {
        padding: {
            top: -20,
            right: 0,
        },
        strokeDashArray: 4,
        yaxis: {
            lines: {
                show: true
            }
        },
        xaxis: {
            lines: {
                strokeDashArray: 0,
                show: true,
            }
        },

    },
};
const averageRevenueChart = new ApexCharts(document.querySelector("#average-revenue"), averageRevenueOptions);
averageRevenueChart.render();