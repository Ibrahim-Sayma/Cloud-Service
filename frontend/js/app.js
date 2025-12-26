const API_URL = "http://localhost:8000";

async function uploadFile() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    if (!file) return alert("Please select a file!");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const response = await fetch(`${API_URL}/files/upload`, {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        alert(result.message);
        loadFiles();
    } catch (error) {
        console.error("Error uploading file:", error);
        alert("Upload failed.");
    }
}

async function loadFiles() {
    try {
        const response = await fetch(`${API_URL}/files/`);
        const files = await response.json();
        const select = document.getElementById('fileSelect');
        select.innerHTML = '<option value="">Select a file...</option>';
        files.forEach(f => {
            const option = document.createElement('option');
            option.value = f.filename;
            option.textContent = `${f.filename} (${f.size} bytes)`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error("Error loading files:", error);
    }
}

async function submitJob() {
    const filename = document.getElementById('fileSelect').value;
    const jobType = document.getElementById('jobType').value;

    if (!filename || !jobType) return alert("Please select a file and job type!");

    let params = {};
    if (jobType === 'ml') {
        const algo = document.getElementById('mlAlgo').value;
        const target = document.getElementById('targetCol').value;
        params = { algorithm: algo, target_col: target };
    }

    try {
        const response = await fetch(`${API_URL}/jobs/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: filename,
                job_type: jobType,
                params: params
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Submission failed");
        }

        const result = await response.json();
        monitorJob(result.job_id);
    } catch (error) {
        console.error("Error submitting job:", error);
        alert(`Error: ${error.message}`);
    }
}

function monitorJob(jobId) {
    const statusDiv = document.getElementById('status-log');
    statusDiv.innerHTML = `Job ${jobId} submitted. Waiting for results...<br>`;

    const interval = setInterval(async () => {
        try {
            const response = await fetch(`${API_URL}/jobs/${jobId}`);
            const status = await response.json();
            if (status && status.status) {
                statusDiv.innerHTML += `Status: ${status.status}<br>`;

                if (status.status === 'COMPLETED') {
                    clearInterval(interval);
                    showResults(jobId);
                } else if (status.status === 'FAILED') {
                    clearInterval(interval);
                    statusDiv.innerHTML += `Job FAILED.`;
                }
            }
        } catch (error) {
            clearInterval(interval);
        }
    }, 2000);
}

async function showResults(jobId) {
    try {
        const response = await fetch(`${API_URL}/jobs/${jobId}/results`);
        const result = await response.json();

        const resultsDiv = document.getElementById('resultsArea');
        resultsDiv.innerHTML = "<h3>Results</h3>";

        // Simple JSON print for now, can be enhanced with Chart.js later
        const pre = document.createElement('pre');
        pre.textContent = JSON.stringify(result, null, 2);
        resultsDiv.appendChild(pre);

    } catch (error) {
        console.error("Error fetching results:", error);
    }
}

// Initial load
window.onload = loadFiles;
