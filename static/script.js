/**
 * 1. GLOBALS & STATE
 */
let currentTable = "";
let myJobChart = null;
let compositionChart = null;
let searchTimeout = null;

// Unified Memory: The search bar uses these to filter regardless of view
let lastData = []; 
let lastConfig = {};

const options = {
    margin: 10,
    filename: 'PESCO_Report.pdf',
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' }
};

function switchView(mode) {
    const tableControls = document.getElementById('table-controls');
    const visualDashboard = document.getElementById('visual-dashboard');
    const salarySlip = document.getElementById('salary-slip-container');

    if (tableControls) tableControls.style.display = 'none';
    if (visualDashboard) visualDashboard.style.display = 'none';
    if (salarySlip) salarySlip.style.display = 'none';

    if (mode === 'table' && tableControls) {
        tableControls.style.display = 'block';
    } else if (mode === 'analytics' && visualDashboard) {
        visualDashboard.style.display = 'block';
    } else if (mode === 'salary' && salarySlip) {
        salarySlip.style.display = 'block';
    }
}

function toggleAnalyticsMenu() {
    const menu = document.getElementById('analytics-options');
    if (!menu) return;
    const isHidden = menu.style.display === 'none' || menu.style.display === '';
    menu.style.display = isHidden ? 'block' : 'none';
    if (isHidden) updateVisualDashboard('Job'); 
}

function resetDashboard() {
    currentTable = "";
    switchView('table');
    const els = ['table-controls', 'visual-dashboard', 'analytics-options'];
    els.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    const title = document.getElementById('page-title');
    const resCount = document.getElementById('resource-count');
    if (title) title.innerText = "Select a Report";
    if (resCount) resCount.innerText = "0";
    document.querySelectorAll('.sidebar button').forEach(btn => btn.classList.remove('active'));
}

async function loadData(name) {
    currentTable = name;
    switchView('table');
    
    document.querySelectorAll('.sidebar button').forEach(btn => {
        btn.classList.remove('active');
        if (btn.getAttribute('onclick')?.includes(name)) btn.classList.add('active');
    });

    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.innerText = name.replace(/_/g, ' ');

    if (name === "Payroll_Register") {
        const pDate = prompt("1/7: Enter Payroll Date (YYYY-MM-DD):", "2026-03-01");
        if (!pDate) return; 

        const pEmp = prompt("2/7: Enter Employee Number (Optional):", "");
        const pSet = prompt("3/7: Enter Assignment Set ID (Optional):", "");
        const pJob = prompt("4/7: Enter Job ID (Optional):", "");
        const pGrade = prompt("5/7: Enter Grade ID (Optional):", "");
        const pOrg = prompt("6/7: Enter Organization ID (Optional):", "");
        const pCity = prompt("7/7: Enter City (Optional):", "");

        let queryObj = new URLSearchParams();
        queryObj.append('date', pDate); 
        
        if (pEmp)   queryObj.append('p_emp_no', pEmp);
        if (pSet)   queryObj.append('set_id', pSet);
        if (pJob)   queryObj.append('p_job_id', pJob);
        if (pGrade) queryObj.append('p_grade_id', pGrade);
        if (pOrg)   queryObj.append('p_org_id', pOrg);
        if (pCity)  queryObj.append('p_city', pCity);
        
        const queryString = `?${queryObj.toString()}`;
        fetchData(queryString);
    } 
    else if (name === "Payroll" || name === "Payroll_Deductions") {
        const userDate = prompt("Enter Payroll Date (YYYY-MM-DD):", "2026-03-01");
        if (!userDate) return; 
        const userSetId = prompt("Enter Assignment Set ID (Optional):", "");
        
        const queryString = `?date=${userDate}&set_id=${userSetId}`;
        fetchData(queryString);
    } 
    else {
        fetchData(); 
    }
}

async function fetchData(params = "") {
    if (!currentTable) return;
    const tableContainer = document.getElementById("table");
    
    if (currentTable.includes("Payroll") || currentTable.includes("Deduction")) {
        if (!params || params === "") {
            const userDate = prompt("Enter Payroll Date (YYYY-MM-DD):", "2026-03-01");
            if (!userDate) {
                tableContainer.innerHTML = "<p style='text-align:center;'>Request Cancelled.</p>";
                return;
            }
            const userSetId = prompt("Enter Assignment Set ID (Optional):", "");
            params = `?date=${userDate}&set_id=${userSetId || ''}`;
        }
    }

    tableContainer.innerHTML = `<div style="text-align:center; padding:50px;"><i class="fas fa-circle-notch fa-spin fa-2x" style="color:#2f81f7;"></i></div>`;
    
    try {
        const res = await fetch(`/api/${currentTable}${params}`);
        const data = await res.json();
        
        if (data.error) throw new Error(data.error);

        lastData = data;
        lastConfig = { isRetirement: currentTable.includes("Retirement") };
        
        renderTable(data);
        updateResourceCount(data);
    } catch (error) {
        console.error("API Error:", error);
        tableContainer.innerHTML = `<p style='color:#f85149; text-align:center;'>Error: ${error.message || "Failed to connect to Oracle API."}</p>`;
    }
}

function updateResourceCount(data) {
    let totalVal = 0;
    if (currentTable === "All_Employees_Data") {
        totalVal = data.length;
    } else {
        totalVal = data.reduce((sum, row) => {
            const workingKey = Object.keys(row).find(key => 
                ["WORKING", "TOTAL_WORKING", "TOTAL WORKING", "COUNT", "TOTAL"].includes(key.toUpperCase())
            );
            return sum + (workingKey ? Number(row[workingKey] || 0) : 0);
        }, 0);
    }
    const countDisplay = document.getElementById('resource-count');
    if (countDisplay) countDisplay.innerText = totalVal.toLocaleString();
}

async function updateVisualDashboard(viewType) {
    switchView('analytics');
    const loader = document.getElementById('dash-loader');
    const content = document.getElementById('dash-content');
    if (loader) loader.style.display = 'block';
    if (content) content.style.display = 'none';

    try {
        let config = { endpoint: '/api/Job_Wise_Vacancy', field: 'DESIGNATION', title: "Job Wise Strength", isRetirement: false };
        
        if (viewType === 'Grade') {
            config = { endpoint: '/api/Grade_Wise_Vacancy', field: 'GRADE', title: "Grade (BPS) Wise Strength", isRetirement: false };
        } else if (viewType === 'Org') {
            config = { endpoint: '/api/Circle_Wise_Vacancy', field: 'CIRCLE_NAME', title: "Circle Wise Strength", isRetirement: false };
        } else if (viewType === 'Retirement') {
            config = { endpoint: '/api/Retirement_Forecast', field: 'RETIREMENT_YEAR', title: "Year-Wise Retirement Forecast", isRetirement: true };
        } else if (viewType === 'Vacancy') {
            config = { 
                endpoint: '/api/vacancy_summary', 
                field: 'DESIGNATION', 
                title: "Officers Vacancy Analysis", 
                isRetirement: false 
            };
        }

        const response = await fetch(config.endpoint);
        const data = await response.json();
        
        const normalizedData = data.map(row => {
            const newRow = {};
            Object.keys(row).forEach(key => {
                const cleanKey = key.toUpperCase().replace(/[\s_]/g, '');
                newRow[cleanKey] = row[key];
            });
            return newRow;
        });

        lastData = normalizedData;
        lastConfig = config;

        refreshDashboardUI(normalizedData, config);
        
        document.getElementById('page-title').innerText = config.title;
        if (loader) loader.style.display = 'none';
        if (content) content.style.display = 'block';
    } catch (err) { 
        console.error("Dashboard Stats Error:", err); 
    }
}

function refreshDashboardUI(data, config) {
    let stats = { w: 0, s: 0, v: 0 };

    if (config.isRetirement && data.length > 0) {
        const yearCols = Object.keys(data[0]).filter(k => k.includes("YEAR") || /^\d{4}$/.test(k));
        stats.w = data.reduce((total, row) => total + yearCols.reduce((s, yr) => s + (Number(row[yr]) || 0), 0), 0);
    } else {
        stats = data.reduce((acc, row) => {
            acc.w += Number(row.TOTALWORKING || row.WORKING || row.COUNT || row.TOTAL || 0);
            acc.s += Number(row.TOTALSANCTIONED || row.SANCTIONED || row.SANCTIONEDSTRENGTH || 0);
            acc.v += Number(row.TOTALVACANT || row.VACANT || row.VACANCY || 0);
            return acc;
        }, {w:0, s:0, v:0});
    }

    if (document.getElementById('dash-total')) document.getElementById('dash-total').innerText = stats.w.toLocaleString();
    if (document.getElementById('resource-count')) document.getElementById('resource-count').innerText = stats.w.toLocaleString();
    if (document.getElementById('dash-sanctioned')) document.getElementById('dash-sanctioned').innerText = config.isRetirement ? "N/A" : stats.s.toLocaleString();
    if (document.getElementById('dash-vacant')) document.getElementById('dash-vacant').innerText = config.isRetirement ? "N/A" : stats.v.toLocaleString();

    renderCharts(data, config);
}

function renderCharts(normalizedData, config) {
    if (myJobChart) myJobChart.destroy();
    if (compositionChart) compositionChart.destroy();
    
    const colors = ['#2f81f7', '#3fb950', '#f85149', '#d29922', '#8957e5', '#00d4ff', '#e83e8c', '#6f42c1', '#fd7e14', '#20c997'];
    let labels = [], chartData = [];

    if (config.isRetirement && normalizedData.length > 0) {
        const yearCols = Object.keys(normalizedData[0]).filter(k => k.includes("YEAR") || /^\d{4}$/.test(k)).sort();
        labels = yearCols.map(col => col.replace(/_/g, ' '));
        chartData = yearCols.map(y => normalizedData.reduce((sum, row) => sum + (Number(row[y]) || 0), 0));
    } else {
        const workingKey = Object.keys(normalizedData[0] || {}).find(k => ["TOTALWORKING", "WORKING", "COUNT", "TOTAL"].includes(k));
        
        const aggregated = normalizedData.reduce((acc, row) => {
            const cleanField = String(config.field || '').toUpperCase().replace(/[\s_]/g, '');
            let key = row[cleanField];
            if (!key) {
                const fallbackKey = Object.keys(row).find(k => k.includes("NAME") || k.includes("GRADE") || k.includes("DESIGNATION"));
                key = row[fallbackKey] || 'Unknown';
            }
            acc[key] = (acc[key] || 0) + Number(row[workingKey] || 0);
            return acc;
        }, {});
        
        let sorted = Object.entries(aggregated);
        if (config.field === 'GRADE') {
            sorted.sort((a, b) => (parseInt(a[0].replace(/\D/g, '')) || 0) - (parseInt(b[0].replace(/\D/g, '')) || 0));
        } else {
            sorted.sort((a, b) => b[1] - a[1]);
        }
        
        if (sorted.length > 20) {
            const top19 = sorted.slice(0, 19);
            const othersSum = sorted.slice(19).reduce((s, e) => s + e[1], 0);
            labels = [...top19.map(e => e[0]), "Others"];
            chartData = [...top19.map(e => e[1]), othersSum];
        } else {
            labels = sorted.map(e => e[0]);
            chartData = sorted.map(e => e[1]);
        }
    }

    myJobChart = new Chart(document.getElementById('jobChart'), {
        type: 'pie',
        data: { labels: labels, datasets: [{ data: chartData, backgroundColor: colors, borderColor: '#1c2128', borderWidth: 2 }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right', labels: { color: '#adbac7', font: { size: 9 } } } } }
    });

    if (!config.isRetirement) renderSecondaryChart(normalizedData);
}

function renderSecondaryChart(normalizedData) {
    const totals = normalizedData.reduce((acc, row) => {
        acc.s += Number(row.TOTALSANCTIONED || row.SANCTIONED || 0);
        acc.w += Number(row.TOTALWORKING || row.WORKING || row.COUNT || row.TOTAL || 0);
        acc.v += Number(row.TOTALVACANT || row.VACANT || 0);
        return acc;
    }, {s:0, w:0, v:0});

    compositionChart = new Chart(document.getElementById('compositionChart'), {
        type: 'bar',
        data: { labels: ['Sanctioned', 'Working', 'Vacant'], datasets: [{ data: [totals.s, totals.w, totals.v], backgroundColor: ['#3fb950', '#2f81f7', '#f85149'] }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
    });
}

function filterTable() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const input = document.getElementById("search");
        if (!input) return;
        const filter = input.value.toUpperCase().trim();

        const visualDashboard = document.getElementById('visual-dashboard');
        const isVisual = visualDashboard && visualDashboard.style.display !== 'none';

        if (isVisual) {
            if (!lastData) return;
            const filteredData = lastData.filter(row => 
                Object.values(row).some(val => String(val).toUpperCase().includes(filter))
            );
            refreshDashboardUI(filteredData, lastConfig);
        } else {
            const table = document.querySelector("#table table");
            if (!table) return;
            const trs = table.getElementsByTagName("tr");
            let visibleCount = 0;

            for (let i = 1; i < trs.length; i++) {
                const isMatch = trs[i].textContent.toUpperCase().indexOf(filter) > -1;
                trs[i].style.display = isMatch ? "" : "none";
                if (isMatch) {
                    if (currentTable === "All_Employees_Data") visibleCount++;
                    else {
                        const cells = trs[i].getElementsByTagName("td");
                        const val = parseInt(cells[cells.length - 1]?.innerText.replace(/,/g, '')) || 0;
                        visibleCount += val;
                    }
                }
            }
            const countDisplay = document.getElementById('resource-count');
            if (countDisplay) countDisplay.innerText = visibleCount.toLocaleString();
        }
    }, 400); 
}

function renderTable(data) {
    const tableDiv = document.getElementById("table");
    const totalBadge = document.querySelector(".info-badge span");

    if (!tableDiv || !data || data.length === 0) {
        tableDiv.innerHTML = "<p style='text-align:center;'>No records found.</p>";
        if(totalBadge) totalBadge.innerText = "0";
        return;
    }

    const columns = Object.keys(data[0]);
    const grossKey = columns.find(k => k.toUpperCase() === 'GROSS_PAY');
    const netKey = columns.find(k => k.toUpperCase() === 'NET_SALARY');

    let totalGross = 0;
    let totalNet = 0;

    data.forEach(row => {
        totalGross += parseFloat(row[grossKey]) || 0;
        totalNet += parseFloat(row[netKey]) || 0;
    });

    if(totalBadge) {
        totalBadge.innerText = totalNet.toLocaleString(undefined, {minimumFractionDigits: 0});
    }

    let tableHtml = `
        <div class="table-container" style="overflow-x:auto; max-height:75vh;">
            <table style="width: 100%; min-width: 3000px; border-collapse: collapse;">
                <thead>
                    <tr>${columns.map(col => `<th>${col.replace(/_/g, ' ')}</th>`).join('')}</tr>
                </thead>
                <tbody>
                    ${data.map(row => `
                        <tr>
                            ${columns.map(col => `<td>${row[col] ?? '-'}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
                <tfoot style="position: sticky; bottom: 0; background: #0d1117; z-index: 5;">
                    <tr style="border-top: 2px solid #30363d; font-weight: bold;">
                        ${columns.map(col => {
                            if (col === columns[0]) return `<td style="padding:12px; color: #8b949e;">TOTAL (${data.length})</td>`;
                            if (col === grossKey) return `<td style="text-align:right; color: #3fb950; padding:12px;">${totalGross.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>`;
                            if (col === netKey) return `<td style="text-align:right; color: #58a6ff; padding:12px;">${totalNet.toLocaleString(undefined, {minimumFractionDigits: 2})}</td>`;
                            return `<td></td>`;
                        }).join('')}
                    </tr>
                </tfoot>
            </table>
        </div>
    `;

    tableDiv.innerHTML = tableHtml;
}

function renderSalarySlip(data, inputMonth) {
    const container = document.getElementById('salary-slip-container');
    if (!data || data.length === 0) return;

    container.style.display = 'block';
    container.style.height = 'auto'; 
    container.style.padding = '20px';

    const d = Object.fromEntries(
        Object.entries(data[0]).map(([k, v]) => [k.toUpperCase().trim(), v])
    );

    // Determine the display month: use inputMonth if provided, else from data, else "N/A"
    const displayMonth = (d.PAYROLL_MONTH || "N/A").toString().toUpperCase();

    const metaKeys = new Set([
        'EMPLOYEE_NUMBER', 'EMPLOYEE_NAME', 'CNIC', 'DEPARTMENT', 
        'DESIGNATION', 'GRADE', 'PAYROLL_MONTH', 'PAYROLL_DATE', 
        'GP_FUND', 'GROSS_PAY', 'TOTAL_DEDUCTION', 'NET_SALARY'
    ]);

    const deductionKeys = new Set([
        'INCOME_TAX', 'GOVT_PROVIDENT_FUND', 'WAPDA_WELFARE_FUND', 
        'GLI_DEDUCTION', 'UNION_FUND', 'HOUSE_RENT_DEDUCTION', 
        'MISC_RECOVERY', 'BUS_CHARGES', 'BENEVOLENT_FUND'
    ]);

    let earningsHTML = "";
    let deductionsHTML = "";

    Object.keys(d).forEach(key => {
        const val = Number(String(d[key] || 0).replace(/,/g, ''));
        if (val > 0 && !metaKeys.has(key)) {
            const rowStr = `
                <div style="display:flex; justify-content:space-between; padding: 4px 0; border-bottom: 1px solid #f0f0f0; font-size: 11px;">
                    <span style="text-transform: uppercase;">${key.replace(/_/g, ' ')}</span>
                    <span style="font-family: monospace; font-weight: bold;">${val.toLocaleString()}</span>
                </div>`;
            
            if (deductionKeys.has(key)) deductionsHTML += rowStr;
            else earningsHTML += rowStr;
        }
    });

    container.innerHTML = `
        <div style="text-align: right; max-width: 800px; margin: 0 auto 10px auto;">
            <button onclick="downloadSlipPDF('${d.EMPLOYEE_NUMBER}_${displayMonth}')" 
                    style="background: #238636; color: white; border: none; padding: 8px 15px; border-radius: 6px; cursor: pointer; font-weight: bold;">
                <i class="fas fa-file-pdf"></i> Download PDF
            </button>
        </div>

        <div id="slip-print-area" style="background:white; color:black; font-family: 'Arial', sans-serif; width: 100%; max-width: 800px; margin: auto; border: 2px solid #000; padding: 30px;">
            <div style="text-align:center; border-bottom: 2px solid #000; margin-bottom: 15px; padding-bottom: 10px;">
                <h2 style="margin:0; font-size: 20px;">PESHAWAR ELECTRIC SUPPLY COMPANY</h2>
                <div style="font-weight:bold; font-size: 14px; margin-top: 5px;">Salary for the month of ${displayMonth}</div>
            </div>

            <table style="width:100%; font-size: 12px; margin-bottom: 15px; border-collapse: collapse;">
                <tr>
                    <td style="padding: 5px; border-bottom: 1px solid #eee;"><strong>Name:</strong> ${d.EMPLOYEE_NAME || 'N/A'}</td>
                    <td style="padding: 5px; border-bottom: 1px solid #eee;"><strong>Emp No:</strong> ${d.EMPLOYEE_NUMBER || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; border-bottom: 1px solid #eee;"><strong>CNIC:</strong> ${d.CNIC || 'N/A'}</td>
                    <td style="padding: 5px; border-bottom: 1px solid #eee;"><strong>Dept:</strong> ${d.DEPARTMENT || 'N/A'}</td>
                </tr>
                <tr>
                    <td style="padding: 5px;"><strong>Grade:</strong> ${d.GRADE || 'N/A'}</td>
                    <td style="padding: 5px;"><strong>GP Fund No:</strong> ${d.GP_FUND || 'N/A'}</td>
                </tr>
            </table>

            <div style="display: flex; border: 1.5px solid black; min-height: 280px;">
                <div style="flex: 1.2; border-right: 1.5px solid black; padding: 10px;">
                    <div style="text-align:center; font-weight:bold; background:#eee; font-size:11px; border-bottom:1px solid black; margin-bottom:8px; padding: 2px;">EARNINGS</div>
                    ${earningsHTML}
                    <div style="border-top: 1.5px solid black; margin-top: 15px; padding-top: 8px; display: flex; justify-content: space-between; font-weight: bold; font-size: 13px;">
                        <span>GROSS CLAIM:</span>
                        <span>Rs. ${Number(d.GROSS_PAY || 0).toLocaleString()}</span>
                    </div>
                </div>

                <div style="flex: 1; padding: 10px;">
                    <div style="text-align:center; font-weight:bold; background:#eee; font-size:11px; border-bottom:1px solid black; margin-bottom:8px; padding: 2px;">DEDUCTIONS</div>
                    ${deductionsHTML}
                    <div style="border-top: 1.5px solid black; margin-top: 15px; padding-top: 8px; display: flex; justify-content: space-between; font-weight: bold; font-size: 13px;">
                        <span>TOTAL DED:</span>
                        <span>Rs. ${Number(d.TOTAL_DEDUCTION || 0).toLocaleString()}</span>
                    </div>
                </div>
            </div>

            <div style="margin-top: 15px; border: 2.2px solid black; padding: 8px 15px; background: #fdfdfd; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-size: 14px; font-weight: bold;">NET AMOUNT PAYABLE:</span>
                <span style="font-size: 18px; font-weight: 900;">Rs. ${Number(d.NET_SALARY || 0).toLocaleString()}</span>
            </div>
        </div>
    `;
}

function showSalarySlipView() {
    const tableControls = document.getElementById('table-controls');
    const visualDashboard = document.getElementById('visual-dashboard');
    const salarySlipContainer = document.getElementById('salary-slip-container');

    if (tableControls) tableControls.style.display = 'none';
    if (visualDashboard) visualDashboard.style.display = 'none';
    
    if (salarySlipContainer) {
        salarySlipContainer.style.display = 'block';
        salarySlipContainer.innerHTML = '<p style="text-align:center;">Loading Slip...</p>';
    }

    document.getElementById('page-title').innerText = 'Employee Salary Slip';

    const empNo = prompt("Enter Employee Number:");
    if (!empNo) return;
    const pDate = prompt("Enter Date (e.g., 01-OCT-2025):", "01-OCT-2025");
    if (!pDate) return;

    fetch(`/api/Salary_Slip?emp_no=${empNo}&date=${pDate}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) throw new Error(data.error);
            renderSalarySlip(data);
        })
        .catch(err => {
            salarySlipContainer.innerHTML = `<p style="color:red; text-align:center;">${err.message}</p>`;
        });
}

function downloadSlipPDF(fileName) {
    const element = document.getElementById('slip-print-area');
    const opt = {
        margin:       0.5,
        filename:     `Salary_Slip_${fileName}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, logging: false, letterRendering: true },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };
    html2pdf().set(opt).from(element).save();
}

function downloadExcel() {
    const table = document.querySelector("#table table");
    if (!table) return alert("No data to export.");
    let csv = [];
    const rows = table.querySelectorAll("tr");
    rows.forEach(row => {
        if (row.style.display !== 'none') {
            csv.push(Array.from(row.querySelectorAll("td, th")).map(c => `"${c.innerText.replace(/"/g, '""')}"`).join(","));
        }
    });
    const blob = new Blob([csv.join("\n")], { type: 'text/csv' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${currentTable || 'Report'}.csv`;
    link.click();
}

async function downloadPDF() {
    const isAnalytics = document.getElementById('visual-dashboard')?.style.display === 'block';
    const sourceId = isAnalytics ? 'visual-dashboard' : 'table';
    const element = document.getElementById(sourceId);
    if (!element || element.innerText.trim() === "") return;
    const reportName = (document.getElementById('page-title')?.innerText || "PESCO_Report").replace(/\s+/g, '_');
    const pdfOptions = {
        margin: [10, 10, 10, 10],
        filename: `${reportName}.pdf`,
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'landscape' },
        pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
    };
    const originalStyle = element.getAttribute('style');
    element.style.backgroundColor = "white";
    element.style.color = "black";
    try { await html2pdf().set(pdfOptions).from(element).toPdf().get('pdf').save(); } 
    catch (e) { console.error(e); } 
    finally { element.style.cssText = originalStyle || ""; }
}

function togglePayrollMenu() {
    const menu = document.getElementById('payroll-analytics-options');
    if (!menu) return;
    const isHidden = menu.style.display === 'none' || menu.style.display === '';
    
    const mainAnalytics = document.getElementById('analytics-options');
    if (mainAnalytics) mainAnalytics.style.display = 'none';
    
    menu.style.display = isHidden ? 'block' : 'none';
    if (isHidden) updatePayrollDashboard('Payroll'); 
}

async function updatePayrollDashboard(viewType) {
    switchView('analytics');
    const loader = document.getElementById('dash-loader');
    const content = document.getElementById('dash-content');
    if (loader) loader.style.display = 'block';
    if (content) content.style.display = 'none';

    try {
        const userDate = prompt("Enter Payroll Date (YYYY-MM-DD):", "2026-03-01");
        if (!userDate) return;

        let config = { 
            endpoint: viewType === 'Payroll' ? `/api/Payroll` : `/api/Payroll_Deductions`,
            title: viewType === 'Payroll' ? "Payroll Earnings Analytics" : "Payroll Deductions Analytics",
            isPayroll: true 
        };

        const response = await fetch(`${config.endpoint}?date=${userDate}`);
        const data = await response.json();

        lastData = data;
        lastConfig = config;

        refreshPayrollUI(data, config);

        document.getElementById('page-title').innerText = config.title;
        if (loader) loader.style.display = 'none';
        if (content) content.style.display = 'block';
    } catch (err) {
        console.error("Payroll Dashboard Error:", err);
    }
}

function refreshPayrollUI(data, config) {
    const valKey = Object.keys(data[0] || {}).find(k => /AMOUNT|VALUE|TOTAL/i.test(k));
    const labelKey = Object.keys(data[0] || {}).find(k => /NAME|HEAD|ELEMENT|TYPE/i.test(k));

    const totalAmount = data.reduce((sum, row) => sum + (Number(row[valKey]) || 0), 0);

    const countDisplay = document.getElementById('resource-count');
    const dashTotal = document.getElementById('dash-total');
    
    if (countDisplay) countDisplay.innerText = "PKR " + totalAmount.toLocaleString();
    if (dashTotal) dashTotal.innerText = totalAmount.toLocaleString();

    if (document.getElementById('dash-sanctioned')) document.getElementById('dash-sanctioned').innerText = "N/A";
    if (document.getElementById('dash-vacant')) document.getElementById('dash-vacant').innerText = "N/A";

    renderPayrollCharts(data, labelKey, valKey);
}

function renderPayrollCharts(data, labelKey, valKey) {
    if (myJobChart) myJobChart.destroy();
    if (compositionChart) {
        document.getElementById('compositionChart').parentElement.style.display = 'none';
    } else {
        const compContainer = document.getElementById('compositionChart')?.parentElement;
        if (compContainer) compContainer.style.display = 'block';
    }

    const colors = ['#2f81f7', '#3fb950', '#f85149', '#d29922', '#8957e5', '#00d4ff', '#e83e8c', '#6f42c1'];
    
    myJobChart = new Chart(document.getElementById('jobChart'), {
        type: 'pie',
        data: {
            labels: data.map(d => d[labelKey]),
            datasets: [{
                data: data.map(d => Number(d[valKey]) || 0),
                backgroundColor: colors,
                borderColor: '#1c2128',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#adbac7', font: { size: 10 } }
                }
            }
        }
    });
}

function loadVacancyDashboard() {
    const content = document.getElementById('content-area');
    content.innerHTML = `
        <h3>Vacancy Analysis (Scale 17 & 18)</h3>
        <div class="row">
            <div class="col-md-8"><canvas id="vacancyBarChart"></canvas></div>
            <div class="col-md-4"><canvas id="vacancyPieChart"></canvas></div>
        </div>
        <div id="vacancy-table-container"></div>
    `;

    fetch('/api/vacancy_summary') 
        .then(response => response.json())
        .then(data => {
            renderVacancyTable(data); 
            renderVacancyCharts(data);
        });
}

function downloadSlipPDF(fileName) {
    const element = document.getElementById('slip-print-area');
    const opt = {
        margin:       0.5,
        filename:     `Salary_Slip_${fileName}.pdf`,
        image:        { type: 'jpeg', quality: 0.98 },
        html2canvas:  { scale: 2, logging: false, letterRendering: true },
        jsPDF:        { unit: 'in', format: 'letter', orientation: 'portrait' }
    };

    html2pdf().set(opt).from(element).save();
}


async function bulkSalarySlipPrompt() {
    const empNo = prompt("Enter Employee Number (Optional):", "");
    const set_id = prompt("Enter Assignment Set ID:", "");
    let payrollDate = prompt("Enter Payroll Date (Format: DD-MON-YYYY, e.g., 31-JAN-2026):");
    
    if (!payrollDate) return;
    payrollDate = payrollDate.toUpperCase();
    
    if (empNo) {
        showSalarySlipView();
        return;
    }
    
    if (!set_id) {
        alert("Assignment Set ID is required.");
        return;
    }
    
    // Show progress
    const progressDiv = showProgressIndicator();
    
    try {
        // Fetch complete data
        const response = await fetch(`/api/Bulk_Salary_Slips?set_id=${encodeURIComponent(set_id)}&date=${encodeURIComponent(payrollDate)}`);
        const data = await response.json();
        
        if (data.error) throw new Error(data.error);
        
        if (!data || data.length === 0) {
            alert("No records found.");
            removeProgressIndicator(progressDiv);
            return;
        }
        
        updateProgress(progressDiv, 0, data.length);
        
        // Initialize PDF with text mode
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({
            unit: 'mm',
            format: 'a4',
            orientation: 'portrait',
            compress: true
        });
        
        let processedCount = 0;
        
        // Process each record
        for (const record of data) {
            if (processedCount > 0) {
                pdf.addPage();
            }
            
            // Add complete text-based salary slip with Lumpsum Salary
            addCompleteSalarySlipToPDF(pdf, record, payrollDate);
            
            processedCount++;
            
            if (processedCount % 5 === 0) {
                updateProgress(progressDiv, processedCount, data.length);
                await new Promise(resolve => setTimeout(resolve, 10));
            }
        }
        
        const fileName = `Salary_Slips_SetID_${set_id}_${payrollDate}.pdf`;
        pdf.save(fileName);
        
        removeProgressIndicator(progressDiv);
        alert(`✅ PDF Generated Successfully!\n\n📄 ${processedCount} salary slips\n🔍 Fully searchable text (Ctrl+F works)\n💾 Optimized file size\n💰 All allowances including Lumpsum Salary included`);
        
    } catch (err) {
        console.error("Error:", err);
        removeProgressIndicator(progressDiv);
        alert("Error: " + err.message);
    }
}


function addCompleteSalarySlipToPDF(pdf, data, month) {
    pdf.setFont("helvetica");
    
    // Header
    pdf.setFontSize(16);
    pdf.setFont("helvetica", "bold");
    pdf.text("PESHAWAR ELECTRIC SUPPLY COMPANY", 105, 20, { align: "center" });
    
    pdf.setFontSize(12);
    pdf.setFont("helvetica", "normal");
    pdf.text(`Salary Slip for the month of ${month}`, 105, 30, { align: "center" });
    
    pdf.line(20, 35, 190, 35);
    
    // Employee Information
    pdf.setFontSize(10);
    pdf.setFont("helvetica", "bold");
    pdf.text("EMPLOYEE INFORMATION", 20, 45);
    
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(9);
    
    const empInfo = [
        ["Employee Name:", data.EMPLOYEE_NAME || "N/A", "Employee No:", data.EMPLOYEE_NUMBER || "N/A"],
        ["CNIC:", data.CNIC || "N/A", "GP Fund No:", data.GP_FUND || "N/A"],
        ["Designation:", data.DESIGNATION || "N/A", "Grade:", data.GRADE || "N/A"],
        ["Department:", data.DEPARTMENT || "N/A", "Position:", data.POSITION || "N/A"]
    ];
    
    let yPos = 52;
    empInfo.forEach(row => {
        pdf.text(row[0], 20, yPos);
        pdf.text(row[1], 50, yPos);
        pdf.text(row[2], 110, yPos);
        pdf.text(row[3], 140, yPos);
        yPos += 7;
    });
    
    // Earnings Section
    yPos += 5;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "bold");
    pdf.text("EARNINGS", 20, yPos);
    pdf.text("AMOUNT (PKR)", 170, yPos, { align: "right" });
    
    yPos += 5;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    
    // All Earnings - INCLUDING LUMPSUM SALARY
    const earnings = [
        { label: "Basic Salary", value: data.BASIC_SALARY },
        { label: "Personal Pay", value: data.PERSONAL_PAY },
        { label: "House Rent Allowance", value: data.HOUSE_RENT_ALLOWANCE },
        { label: "Cash Medical Allowance", value: data.CASH_MEDICAL_ALLOWANCE },
        { label: "Conveyance Allowance", value: data.CONVEYANCE_ALLOWANCE },
        { label: "Hard Area Allowance", value: data.HARD_AREA_ALLOWANCE },
        { label: "Special Allowance", value: data.SPECIAL_ALLOWANCE },
        { label: "Danger Allowance", value: data.DANGER_ALLOWANCE },
        { label: "WAPDA Special Relief", value: data.WAPDA_SPECIAL_RELIEF_ALLOWANCE },
        { label: "Integrated Allowance", value: data.INTEGRATED_ALLOWANCE },
        { label: "GLI Allowance", value: data.GLI_ALLOWANCE },
        { label: "Misc Arrear", value: data.MISC_ARREAR },
        { label: "Job Allowance", value: data.JOB_ALLOWANCE },
        { label: "Motor Cycle Allowance", value: data.MOTOR_CYCLE_ALLOWANCE },
        { label: "Special Pay", value: data.SPECIAL_PAY },
        { label: "Qualification Pay", value: data.QUALIFICATION_PAY },
        { label: "Entertainment Allowance", value: data.ENTERTAINMENT_ALLOWANCE },
        { label: "Special Security Allowance", value: data.SPECIAL_SECURITY_ALLOWANCE },
        { label: "Headquarter Allowance", value: data.HEADQUARTER_ALLOWANCE },
        { label: "Senior Post Allowance", value: data.SENIOR_POST_ALLOWANCE },
        { label: "Hill Area Allowance", value: data.HILL_AREA_ALLOWANCE },
        { label: "Orderly Allowance", value: data.ORDERLY_ALLOWANCE },
        { label: "GSO Allowance", value: data.GSO_ALLOWANCE },
        { label: "Appointment Allowance", value: data.APPOINTMENT_ALLOWANCE },
        { label: "Kit Allowance", value: data.KIT_ALLOWANCE },
        { label: "Un-Attracted Allowance", value: data.UN_ATTRACTED_ALLOWANCE },
        { label: "Technical Allowance", value: data.TECHNICAL_ALLOWANCE },
        { label: "Transport Subsidy", value: data.TRANSPORT_SUBSIDY },
        { label: "DRA 2021", value: data.DRA21 },
        { label: "DRA 2022", value: data.DRA22 },
        { label: "ARA 2022", value: data.ARA22 },
        { label: "ARA 2023", value: data.ARA23 },
        { label: "ARA 2024", value: data.ARA24 },
        { label: "ARA 2025", value: data.ARA25 },
        { label: "DRA 2025", value: data.DRA25 },
        { label: "Miscellaneous Allowance", value: data.MISCELLANEOUS_ALLOWANCE },
        { label: "Lumpsum Salary", value: data.LUMPSUM_SALARY },  // <-- ADDED HERE
        { label: "Daily Wages Salary", value: data.DAILY_WAGES_SALARY }
    ];
    
    // Use GROSS_PAY from API instead of calculating manually
    // This ensures Lumpsum Salary is included correctly
    let totalEarnings = parseFloat(data.GROSS_PAY) || 0;
    
    // Display individual earnings (only show positive amounts)
    earnings.forEach(item => {
        const amount = parseFloat(item.value) || 0;
        if (amount > 0 && yPos < 260) {
            pdf.text(item.label, 20, yPos);
            pdf.text(amount.toLocaleString(), 170, yPos, { align: "right" });
            yPos += 4;
        }
    });
    
    yPos += 2;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(9);
    pdf.text("GROSS EARNINGS", 20, yPos);
    pdf.text(totalEarnings.toLocaleString(), 170, yPos, { align: "right" });
    
    // Deductions Section
    yPos += 10;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "bold");
    pdf.text("DEDUCTIONS", 20, yPos);
    pdf.text("AMOUNT (PKR)", 170, yPos, { align: "right" });
    
    yPos += 5;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "normal");
    pdf.setFontSize(8);
    
    const deductions = [
        { label: "Income Tax", value: data.INCOME_TAX },
        { label: "Government Provident Fund", value: data.GOVT_PROVIDENT_FUND },
        { label: "WAPDA Welfare Fund", value: data.WAPDA_WELFARE_FUND },
        { label: "GLI Deduction", value: data.GLI_DEDUCTION },
        { label: "Union Fund", value: data.UNION_FUND },
        { label: "Medical Benevolent Fund", value: data.MEDICAL_BENEVOLENT_FUND },
        { label: "House Rent Deduction", value: data.HOUSE_RENT_DEDUCTION },
        { label: "Bus Charges", value: data.BUS_CHARGES },
        { label: "Misc Recovery", value: data.MISC_RECOVERY },
        { label: "GP Fund Advance I", value: data.GP_FUND_ADVANCE_I },
        { label: "GP Fund Advance II", value: data.GP_FUND_ADVANCE_II }
    ];
    
    let totalDeductions = parseFloat(data.TOTAL_DEDUCTION) || 0;
    
    // Display individual deductions (only show positive amounts)
    deductions.forEach(item => {
        const amount = parseFloat(item.value) || 0;
        if (amount > 0 && yPos < 260) {
            pdf.text(item.label, 20, yPos);
            pdf.text(amount.toLocaleString(), 170, yPos, { align: "right" });
            yPos += 4;
        }
    });
    
    yPos += 2;
    pdf.line(20, yPos, 190, yPos);
    yPos += 3;
    
    pdf.setFont("helvetica", "bold");
    pdf.text("TOTAL DEDUCTIONS", 20, yPos);
    pdf.text(totalDeductions.toLocaleString(), 170, yPos, { align: "right" });
    
    // Net Pay - Use NET_SALARY from API
    const netPay = parseFloat(data.NET_SALARY) || (totalEarnings - totalDeductions);
    yPos += 10;
    pdf.setFillColor(240, 240, 240);
    pdf.rect(20, yPos - 3, 170, 10, "F");
    pdf.setFont("helvetica", "bold");
    pdf.setFontSize(11);
    pdf.text("NET PAYABLE AMOUNT", 20, yPos);
    pdf.text("PKR " + netPay.toLocaleString(), 170, yPos, { align: "right" });
    
    // Footer
    pdf.setFontSize(7);
    pdf.setFont("helvetica", "italic");
    pdf.text("This is a computer generated salary slip.", 105, 280, { align: "center" });
    pdf.text(`Generated on: ${new Date().toLocaleString()}`, 105, 285, { align: "center" });
}

function showProgressIndicator() {
    const progressDiv = document.createElement('div');
    progressDiv.id = 'bulk-progress';
    progressDiv.style.cssText = `
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        background: #1c2128; padding: 20px 40px; border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5); z-index: 10000;
        text-align: center; color: white; font-family: Arial, sans-serif;
        min-width: 350px;
    `;
    progressDiv.innerHTML = `
        <div style="margin-bottom: 15px;"><i class="fas fa-spinner fa-pulse fa-2x"></i></div>
        <div id="progress-text">Generating searchable PDF...</div>
        <div style="margin-top: 10px; width: 100%; background: #30363d; border-radius: 4px; overflow: hidden;">
            <div id="progress-bar" style="width: 0%; height: 4px; background: #2f81f7; transition: width 0.3s;"></div>
        </div>
        <div id="progress-detail" style="margin-top: 10px; font-size: 12px; color: #8b949e;"></div>
    `;
    document.body.appendChild(progressDiv);
    return progressDiv;
}

function updateProgress(progressDiv, current, total) {
    const percent = (current / total) * 100;
    const progressBar = progressDiv.querySelector('#progress-bar');
    const progressText = progressDiv.querySelector('#progress-text');
    const progressDetail = progressDiv.querySelector('#progress-detail');
    
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.innerHTML = `Processing ${current} of ${total} salary slips...`;
    if (progressDetail) progressDetail.innerHTML = `${Math.round(percent)}% complete`;
}

function removeProgressIndicator(progressDiv) {
    if (progressDiv && progressDiv.parentNode) {
        progressDiv.parentNode.removeChild(progressDiv);
    }
}
function triggerEmployee360() {
    let userInput = prompt("Enter ERP Number or CNIC (with or without dashes):");
    
    if (userInput && userInput.trim() !== "") {
        fetch(`/get_employee_360_data?search_val=${encodeURIComponent(userInput.trim())}`)
            .then(response => {
                if (!response.ok) throw new Error("ID not found or database error.");
                return response.json();
            })
            .then(data => {
                generate360PDF(data);
            })
            .catch(err => {
                alert("System Message: " + err.message);
            });
    }
}

function generate360PDF(data) {
    const photoBaseUrl = window.location.origin + "/static/emp_photos/"; 
    
    // Fallback for profile picture
    const profileImgUrl = data.employee_number 
        ? `${photoBaseUrl}${data.employee_number.toString().trim()}.jpg` 
        : `https://ui-avatars.com/api/?name=${data.first_name}+${data.last_name}&background=007bff&color=fff`;

    const getBase64Image = (url) => fetch(url)
        .then(response => response.ok ? response.blob() : Promise.reject())
        .then(blob => new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.readAsDataURL(blob);
        }))
        .catch(() => `https://ui-avatars.com/api/?name=${data.first_name}+${data.last_name}&background=0056b3&color=fff`);

    getBase64Image(profileImgUrl).then(base64Img => {
        const element = document.createElement('div');
        element.style.width = "1050px"; 
        element.style.padding = "40px";
        element.style.background = "#fff";

        const fullName = [data.first_name, data.middle_names, data.last_name]
            .filter(n => n && n.trim() !== "").join(" ");

// 1. Build Training Rows (Restored Logic)
        let trainingRows = "";
        if (data.trainings && data.trainings.length > 0) {
            data.trainings.forEach(tr => {
                trainingRows += `
                    <tr style="border-bottom: 1px solid #eee; font-size: 10pt; page-break-inside: avoid; color: #000;">
                        <td style="padding: 10px; width: 75%;"><strong>${tr.name}</strong></td>
                        <td style="padding: 10px; width: 25%; text-align: right; color: #333;">${tr.date || 'N/A'}</td>
                    </tr>`;
            });
        } else {
            trainingRows = `<tr><td colspan="2" style="padding:15px; text-align:center; color: #333;">No professional training records found.</td></tr>`;
        }

        // 2. Build Assignment Rows
        let assignmentRows = "";
        if (data.assignments && data.assignments.length > 0) {
            data.assignments.forEach(asg => {
                assignmentRows += `
                    <tr style="border-bottom: 1px solid #eee; font-size: 10pt; page-break-inside: avoid; color: #000;">
                        <td style="padding: 10px; width: 25%;"><strong>${asg.designation}</strong></td>
                        <td style="padding: 10px; width: 10%;">${asg.grade}</td>
                        <td style="padding: 10px; width: 35%;">${asg.office}</td>
                        <td style="padding: 10px; width: 30%; color: #333; font-size: 9pt; text-align: right; white-space: nowrap;">
                            ${asg.from_date} to ${asg.to_date}
                        </td>
                    </tr>`;
            });
        } else {
            assignmentRows = `<tr><td colspan="4" style="padding:20px; text-align:center; color: #000;">No assignment history found.</td></tr>`;
        }

        // 3. Update the HTML (Adding Training Section before the Footer)
        element.innerHTML = `
            <div style="border: 2px solid #0056b3; padding: 25px; font-family: Arial, sans-serif; color: #000;">
                <table style="width: 100%; border-bottom: 3px solid #0056b3; margin-bottom: 20px; padding-bottom: 15px;">
                    <tr>
                        <td style="vertical-align: top; width: 75%;">
                            <h1 style="color: #0056b3; margin: 0; font-size: 26pt; text-transform: uppercase;">Employee 360° Profile</h1>
                            <p style="color: #333; margin: 5px 0; font-size: 12pt;">PESCO Strategic HRIS Dashboard Report</p>
                            
                            <div style="margin-top: 20px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; line-height: 1.6; color: #000;">
                                <div>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Name:</strong> ${fullName}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Father Name:</strong> ${data.father_name || 'N/A'}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>ERP Number:</strong> ${data.employee_number}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>GP Fund No:</strong> ${data.gpf_no || 'N/A'}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Cadre:</strong> <span style="color: #0056b3;">${data.cadre || 'N/A'}</span></p>
                                </div>
                                <div>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>CNIC:</strong> ${data.national_identifier}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Contact No:</strong> ${data.contact_no || 'N/A'}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Qualification:</strong> ${data.qualification || 'N/A'}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Joining:</strong> ${data.hire_date || 'N/A'}</p>
                                    <p style="margin: 2px 0; font-size: 11pt;"><strong>Retirement:</strong> <span style="color: #d9534f; font-weight: bold;">${data.retirement_date}</span></p>
                                </div>
                            </div>
                        </td>
                        <td style="vertical-align: top; text-align: right; width: 25%;">
                            <img src="${base64Img}" style="width: 140px; height: 160px; border: 3px solid #0056b3; border-radius: 4px; object-fit: cover;">
                        </td>
                    </tr>
                </table>

                <h3 style="background: #e9f2ff; padding: 10px; color: #0056b3; border-left: 6px solid #0056b3; font-size: 14pt; margin: 20px 0 10px 0;">Career & Assignment History</h3>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px; color: #000;">
                    <thead>
                        <tr style="background: #f8f9fa; border-bottom: 2px solid #0056b3; text-align: left; font-size: 9pt; color: #000;">
                            <th style="padding: 10px;">Designation</th>
                            <th style="padding: 10px;">Grade</th>
                            <th style="padding: 10px;">Office</th>
                            <th style="padding: 10px; text-align: right;">Tenure</th>
                        </tr>
                    </thead>
                    <tbody>${assignmentRows}</tbody>
                </table>

                <h3 style="background: #e9f2ff; padding: 10px; color: #0056b3; border-left: 6px solid #0056b3; font-size: 14pt; margin: 20px 0 10px 0;">Professional Training History</h3>
                <table style="width: 100%; border-collapse: collapse; color: #000;">
                    <thead>
                        <tr style="background: #f8f9fa; border-bottom: 2px solid #0056b3; text-align: left; font-size: 9pt; color: #000;">
                            <th style="padding: 10px;">Course Title</th>
                            <th style="padding: 10px; text-align: right;">Date / Period</th>
                        </tr>
                    </thead>
                    <tbody>${trainingRows}</tbody>
                </table>

                <div style="margin-top: 30px; text-align: center; font-size: 9px; color: #333; border-top: 1px solid #eee; padding-top: 10px;">
                    Generated by PESCO EBS HRIS Dashboard | ${new Date().toLocaleString()}
                </div>
            </div>`;

        const opt = {
            margin: 0.3,
            filename: `360_Profile_${data.employee_number}_Landscape.pdf`,
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: { scale: 2, useCORS: true },
            jsPDF: { unit: 'in', format: 'a4', orientation: 'landscape' }
        };

        html2pdf().set(opt).from(element).save();
    });
}
