const data = window.dashboardData || {categories:{}};
const labels = Object.keys(data.categories || {});
const values = Object.values(data.categories || {});
if (document.getElementById('categoryChart') && labels.length) {
  new Chart(document.getElementById('categoryChart'), {
    type: 'doughnut', data: {labels, datasets:[{data:values, borderWidth:3, borderColor:'#ffffff'}]},
    options:{responsive:true, maintainAspectRatio:false, plugins:{legend:{position:'bottom', labels:{usePointStyle:true, padding:18}}}, cutout:'68%'}
  });
}
