document.addEventListener("DOMContentLoaded", function() {
    let totalLinear = 0, totalEstimation = 0, totalCompleted = 0, totalPending = 0, totalTimeTaken = 0, totalCountVal = 0, partCount = 0;
    let uniquePeople = new Set(), uniqueBikeLines = new Set(), personData = {};

    const rows = document.querySelectorAll('.record-row');
    rows.forEach(row => {
        const linear = parseFloat(row.getAttribute('data-linear')) || 0;
        const estimation = parseFloat(row.getAttribute('data-estimation')) || 0;
        const completed = parseFloat(row.getAttribute('data-completed')) || 0;
        const pending = parseFloat(row.getAttribute('data-pending')) || 0;
        const timeTaken = parseFloat(row.getAttribute('data-timetaken')) || 0;
        const countVal = parseInt(row.getAttribute('data-countval')) || 0;
        const employee = row.getAttribute('data-employee').trim();
        const bikeLineCell = row.cells[1].innerText.trim();

        totalLinear += linear; 
        totalEstimation += estimation; 
        totalCompleted += completed;
        totalPending += pending; 
        totalTimeTaken += timeTaken; 
        totalCountVal += countVal; 
        partCount++; 

        if (employee && employee !== "Unassigned") uniquePeople.add(employee);
        if (bikeLineCell) uniqueBikeLines.add(bikeLineCell);

        let empKey = employee || "Unassigned";
        if (!personData[empKey]) personData[empKey] = { completed: 0, pending: 0 };
        personData[empKey].completed += completed;
        personData[empKey].pending += pending;
    });

    // Update Spreadsheet Footers
    document.getElementById('total-bike-lines').innerText = uniqueBikeLines.size + " Lines";
    document.getElementById('total-parts').innerText = partCount + " Part(s)";
    document.getElementById('total-linear').innerText = totalLinear.toFixed(2) + " KM";
    document.getElementById('total-estimation').innerText = totalEstimation.toFixed(2) + " KM";
    document.getElementById('total-people').innerText = uniquePeople.size + " Allocated";
    document.getElementById('total-completed').innerText = totalCompleted.toFixed(2) + " KM";
    document.getElementById('total-pending').innerText = totalPending.toFixed(2) + " KM";
    document.getElementById('total-time').innerText = totalTimeTaken.toFixed(2) + " Hrs";
    document.getElementById('total-count').innerText = totalCountVal;

    // Parse Data Arrays for Charts
    const employeeNames = Object.keys(personData);
    const employeeCompleted = employeeNames.map(name => personData[name].completed.toFixed(2));
    const employeePending = employeeNames.map(name => personData[name].pending.toFixed(2));

    // Chart 1: Cumulative Operational Metrics Progress
    new Chart(document.getElementById('progressChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: ['Total Operations'],
            datasets: [
                { label: 'Completed KM', data: [totalCompleted.toFixed(2)], backgroundColor: '#10b981' },
                { label: 'Pending KM', data: [totalPending.toFixed(2)], backgroundColor: '#f59e0b' }
            ]
        },
        options: { 
            indexAxis: 'y', 
            responsive: true, 
            plugins: { legend: { position: 'bottom' } }, 
            scales: { x: { stacked: true }, y: { stacked: true } } 
        }
    });

    // Chart 2: Metrics Broken down per User
    new Chart(document.getElementById('personChart').getContext('2d'), {
        type: 'bar',
        data: {
            labels: employeeNames,
            datasets: [
                { label: 'Completed KM', data: employeeCompleted, backgroundColor: '#3b82f6' },
                { label: 'Pending KM', data: employeePending, backgroundColor: '#ef4444' }
            ]
        },
        options: { 
            responsive: true, 
            plugins: { legend: { position: 'bottom' } }, 
            scales: { x: { stacked: true }, y: { stacked: true } } 
        }
    });

    // Real-time Table Filter Search Event Handler
    document.getElementById('tableSearch').addEventListener('input', function(e) {
        const query = e.target.value.toLowerCase().trim();
        rows.forEach(row => {
            const cells = row.querySelectorAll('.searchable-field');
            let match = false;
            cells.forEach(c => { 
                if (c.innerText.toLowerCase().includes(query)) match = true; 
            });
            row.style.display = (match || query === "") ? "" : "none";
        });
    });
});