/**
 * Employee Performance & QC View Interaction Controller
 */
document.addEventListener("DOMContentLoaded", function() {
    initializeQcColumnToggler();
});

function initializeQcColumnToggler() {
    const toggleBtn = document.getElementById("toggleQcView");
    if (!toggleBtn) return;

    toggleBtn.addEventListener("click", function() {
        // Fetch all target header/data cells featuring the matching class marker
        const qcCells = document.querySelectorAll(".qc-col");
        
        if (qcCells.length === 0) return;

        // Determine ongoing operational state based off the first cell visibility
        const currentlyHidden = qcCells[0].classList.contains("hidden-qc-col");

        qcCells.forEach(cell => {
            if (currentlyHidden) {
                cell.classList.remove("hidden-qc-col");
            } else {
                cell.classList.add("hidden-qc-col");
            }
        });

        // Toggle action button UI context states dynamically
        if (currentlyHidden) {
            toggleBtn.textContent = "📋 Hide QC Columns";
            toggleBtn.style.backgroundColor = "#64748b"; // Shifts to neutral color when visible
        } else {
            toggleBtn.textContent = "🔍 Show QC Columns";
            toggleBtn.style.backgroundColor = "#0d9488"; // Reverts to clean dark teal
        }
    });
}