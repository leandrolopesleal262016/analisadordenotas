document.addEventListener('DOMContentLoaded', function() {
    if (typeof summaryData !== 'undefined' && summaryData.length > 0) {
        summaryData.forEach(function(item, index) {
            var ctxPie = document.getElementById('pieChart' + index).getContext('2d');

            var totalValorNF = parseFloat(item['Total Valor NF'].replace('.', '').replace(',', '.'));
            var totalCreditos = parseFloat(item['Total Créditos'].replace('.', '').replace(',', '.'));

            var backgroundColors = totalCreditos === 0 
                ? ['rgba(255, 99, 132, 0.8)', 'rgba(255, 99, 132, 0.8)'] // Vermelho para crédito zero
                : ['rgba(173, 216, 230, 0.8)', 'rgba(75, 192, 192, 0.8)']; // Azul claro para Valor NF e Verde para Créditos

            new Chart(ctxPie, {
                type: 'pie',
                data: {
                    labels: ['Total Valor NF', 'Total Créditos'],
                    datasets: [{
                        label: item['Emitente'],
                        data: [totalValorNF, totalCreditos],
                        backgroundColor: backgroundColors
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            callbacks: {
                                label: function(tooltipItem) {
                                    return tooltipItem.label + ': R$ ' + tooltipItem.raw.toFixed(2);
                                }
                            }
                        },
                        datalabels: {
                            color: '#fff',
                            formatter: function(value, context) {
                                var total = context.chart.data.datasets[0].data.reduce(function(a, b) {
                                    return a + b;
                                }, 0);
                                var percentage = (value / total * 100).toFixed(2) + '%';
                                return percentage;
                            },
                            font: {
                                weight: 'bold',
                                size: '16'
                            }
                        }
                    }
                },
                plugins: [ChartDataLabels]
            });
        });
    }
});
