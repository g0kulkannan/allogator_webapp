// AlloPred Frontend JavaScript

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('prediction-form');
    const sequenceInput = document.getElementById('sequence');
    const seqLengthSpan = document.getElementById('seq-length');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    const resultsSection = document.getElementById('results');
    const errorSection = document.getElementById('error');
    const errorText = document.getElementById('error-text');

    let currentJobId = null;

    // Update sequence length counter
    sequenceInput.addEventListener('input', function() {
        const cleanSeq = this.value.replace(/\s/g, '');
        seqLengthSpan.textContent = cleanSeq.length;
    });

    // Form submission
    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        // Hide previous results/errors
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';

        // Show loading state
        submitBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'inline';

        try {
            const formData = {
                sequence: sequenceInput.value,
                active_residues: document.getElementById('active-residues').value,
                pdb_code: document.getElementById('pdb-code').value || null
            };

            const response = await fetch('/api/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Prediction failed');
            }

            // Store job ID
            currentJobId = data.job_id;

            // Display results
            displayResults(data);

        } catch (error) {
            showError(error.message);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            btnText.style.display = 'inline';
            btnLoading.style.display = 'none';
        }
    });

    function displayResults(data) {
        resultsSection.style.display = 'block';

        // Create the attention plot
        createPlot(data.scores);

        // Populate the table
        populateTable(data.scores);

        // Show/hide PDB download buttons
        const pdbRawBtn = document.getElementById('download-pdb-raw');
        const pdbRankBtn = document.getElementById('download-pdb-rank');

        if (data.has_pdb) {
            pdbRawBtn.style.display = 'inline-block';
            pdbRankBtn.style.display = 'inline-block';
        } else {
            pdbRawBtn.style.display = 'none';
            pdbRankBtn.style.display = 'none';
        }

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function createPlot(scores) {
        // Sort scores by residue number for plotting
        const sortedScores = [...scores].sort((a, b) => a.residue - b.residue);

        const residues = sortedScores.map(s => s.residue);
        const rawScores = sortedScores.map(s => s.raw_score);
        const aminoAcids = sortedScores.map(s => s.amino_acid);
        const rankScores = sortedScores.map(s => s.rank_score);

        // Custom hover text
        const hoverText = sortedScores.map(s =>
            `Residue: ${s.residue}<br>` +
            `Amino Acid: ${s.amino_acid}<br>` +
            `Raw Score: ${s.raw_score.toFixed(4)}<br>` +
            `Rank Score: ${s.rank_score.toFixed(1)}%`
        );

        const trace = {
            x: residues,
            y: rawScores,
            type: 'scatter',
            mode: 'lines+markers',
            marker: {
                size: 6,
                color: rankScores,
                colorscale: 'Plasma',
                showscale: true,
                colorbar: {
                    title: 'Rank Score (%)',
                    titleside: 'right'
                }
            },
            line: {
                color: '#667eea',
                width: 1
            },
            text: hoverText,
            hoverinfo: 'text'
        };

        const layout = {
            title: {
                text: 'Attention Score by Residue',
                font: { size: 18 }
            },
            xaxis: {
                title: 'Residue Number',
                tickfont: { size: 12 }
            },
            yaxis: {
                title: 'Attention Score',
                tickfont: { size: 12 }
            },
            hovermode: 'closest',
            margin: { t: 50, b: 50, l: 60, r: 20 }
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d']
        };

        Plotly.newPlot('attention-plot', [trace], layout, config);
    }

    function populateTable(scores) {
        const tbody = document.querySelector('#scores-table tbody');
        tbody.innerHTML = '';

        // Sort by rank score (descending) for the table
        const sortedScores = [...scores].sort((a, b) => b.rank_score - a.rank_score);

        sortedScores.forEach(score => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${score.residue}</td>
                <td>${score.amino_acid}</td>
                <td>${score.raw_score.toFixed(6)}</td>
                <td>${score.rank_score.toFixed(1)}%</td>
            `;
            tbody.appendChild(row);
        });
    }

    function showError(message) {
        errorText.textContent = message;
        errorSection.style.display = 'block';
        errorSection.scrollIntoView({ behavior: 'smooth' });
    }

    // Download button handlers
    document.getElementById('download-csv').addEventListener('click', function() {
        if (currentJobId) {
            window.location.href = `/api/download/csv/${currentJobId}`;
        }
    });

    document.getElementById('download-pdb-raw').addEventListener('click', function() {
        if (currentJobId) {
            window.location.href = `/api/download/pdb_raw/${currentJobId}`;
        }
    });

    document.getElementById('download-pdb-rank').addEventListener('click', function() {
        if (currentJobId) {
            window.location.href = `/api/download/pdb_rank/${currentJobId}`;
        }
    });
});
