/*
Template Name: Dusty - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: Widgets Js
*/

// 
// Chart Boarding Opened
// 
const chartBoardingOpenedOptions = {
    series: [60],
    chart: {
        height: 90,
        width: 90,
        parentHeightOffset: 0,
        type: 'radialBar'
    },
    plotOptions: {
        radialBar: {
            endAngle: 360,
            offsetX: 20,
            offsetY: [0],
            hollow: {
                margin: 0,
                size: '40%',
            },
            dataLabels: {
                show: false,
            },
            track: {
                show: true,
                background: '#adb5bd'
            },
        },
    },
    stroke: {
        lineCap: "round",
    }
};
const chartBoardingOpenedChart = new ApexCharts(document.querySelector("#chart-boarding-opened"), chartBoardingOpenedOptions);
chartBoardingOpenedChart.render();

// 
// Chart Boarding clicked
// 
const chartBoardingClickedOptions = {
    series: [72],
    chart: {
        height: 90,
        width: 90,
        parentHeightOffset: 0,
        type: 'radialBar'
    },
    plotOptions: {
        radialBar: {
            endAngle: 360,
            offsetX: 20,
            offsetY: [0],
            hollow: {
                margin: 0,
                size: '40%',
            },
            dataLabels: {
                show: false,
            },
            track: {
                show: true,
                background: '#adb5bd'
            },
        },
    },
    stroke: {
        lineCap: "round",
    }
};
const chartBoardingClickedChart = new ApexCharts(document.querySelector("#chart-boarding-clicked"), chartBoardingClickedOptions);
chartBoardingClickedChart.render();

// 
// Chart Boarding converted
// 
const chartBoardingConvertedOptions = {
    chart: {
        type: "line",
        height: 25,
        width: 90,
        sparkline: {
            enabled: true
        },
        animations: {
            enabled: false
        },
    },
    fill: {
        opacity: 1,
    },
    stroke: {
        width: [3],
        lineCap: "round",
        curve: "straight",
    },
    series: [{
        name: "May",
        data: [40, 40, 115, 90, 65, 85, 50, 75, 90, 119]
    }],
    tooltip: {
        theme: 'light'
    },
    xaxis: {
        labels: {
            padding: 0,
        },
        tooltip: {
            enabled: false
        },
        type: 'datetime',
    },
    yaxis: {
        labels: {
            padding: 4
        },
    },
    labels: [
        '2020-06-21', '2020-06-22', '2020-06-23', '2020-06-24', '2020-06-25', '2020-06-26', '2020-06-27', '2020-06-28', '2020-06-29',
    ],
    colors: ["#f59440"],
    legend: {
        show: false,
    },
};
const chartBoardingConvertedChart = new ApexCharts(document.querySelector("#chart-boarding-converted"), chartBoardingConvertedOptions);
chartBoardingConvertedChart.render();

// 
// Chart Boarding Delivered
//
const chartBoardingDeliveredOptions = {
    chart: {
        type: "line",
        height: 25,
        width: 90,
        sparkline: {
            enabled: true
        },
        animations: {
            enabled: false
        },
    },
    fill: {
        opacity: 1,
    },
    stroke: {
        width: [3],
        lineCap: "round",
        curve: "straight",
    },
    series: [{
        name: "May",
        data: [40, 40, 115, 90, 65, 85, 50, 75, 90, 119]
    }],
    tooltip: {
        theme: 'light'
    },
    xaxis: {
        labels: {
            padding: 0,
        },
        tooltip: {
            enabled: false
        },
        type: 'datetime',
    },
    yaxis: {
        labels: {
            padding: 4
        },
    },
    labels: [
        '2020-06-21', '2020-06-22', '2020-06-23', '2020-06-24', '2020-06-25', '2020-06-26', '2020-06-27', '2020-06-28', '2020-06-29',
    ],
    colors: ["#522c8f"],
    legend: {
        show: false,
    },
};
const chartBoardingDeliveredChart = new ApexCharts(document.querySelector("#chart-boarding-delivered"), chartBoardingDeliveredOptions);
chartBoardingDeliveredChart.render();