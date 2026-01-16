// AlloGator Frontend JavaScript

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
        // Show results section first so Plotly can measure dimensions
        resultsSection.style.display = 'block';

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

        // Populate the table first
        populateTable(data.scores);

        // Create the attention plot after a small delay to ensure DOM is ready
        setTimeout(function() {
            createPlot(data.scores);
        }, 100);

        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function createPlot(scores) {
        // Check if we have scores
        if (!scores || scores.length === 0) {
            console.error('No scores to plot');
            document.getElementById('attention-plot').innerHTML = '<p style="text-align: center; padding: 50px;">No scores available to plot.</p>';
            return;
        }

        // Check if Plotly is loaded
        if (typeof Plotly === 'undefined') {
            console.error('Plotly not loaded');
            document.getElementById('attention-plot').innerHTML = '<p style="text-align: center; padding: 50px;">Error: Plotly library not loaded.</p>';
            return;
        }

        // Sort scores by residue number for plotting
        const sortedScores = [...scores].sort((a, b) => a.residue - b.residue);

        const residues = sortedScores.map(s => s.residue);
        const rawScores = sortedScores.map(s => s.raw_score);
        const rankScores = sortedScores.map(s => s.rank_score);

        // Custom hover text
        const hoverText = sortedScores.map(s =>
            'Residue: ' + s.residue + '<br>' +
            'Amino Acid: ' + s.amino_acid + '<br>' +
            'Raw Score: ' + s.raw_score.toFixed(4) + '<br>' +
            'Rank Score: ' + s.rank_score.toFixed(1) + '%'
        );

        const trace = {
            x: residues,
            y: rawScores,
            type: 'scatter',
            mode: 'lines+markers',
            marker: {
                size: 8,
                color: rankScores,
                colorscale: 'Viridis',
                reversescale: true,
                showscale: true,
                colorbar: {
                    title: {
                        text: 'Rank (%)',
                        side: 'right'
                    },
                    thickness: 15
                }
            },
            line: {
                color: 'rgba(46, 125, 50, 0.3)',
                width: 1
            },
            text: hoverText,
            hoverinfo: 'text',
            hoverlabel: {
                bgcolor: 'white',
                bordercolor: '#2e7d32',
                font: { size: 12 }
            }
        };

        const layout = {
            title: {
                text: 'Attention Score by Residue Position',
                font: { size: 16, color: '#333' }
            },
            xaxis: {
                title: {
                    text: 'Residue Number',
                    font: { size: 14 }
                },
                tickfont: { size: 11 },
                gridcolor: '#e0e0e0',
                zeroline: false
            },
            yaxis: {
                title: {
                    text: 'Attention Score (sum to active site)',
                    font: { size: 14 }
                },
                tickfont: { size: 11 },
                gridcolor: '#e0e0e0',
                zeroline: false
            },
            hovermode: 'closest',
            margin: { t: 60, b: 60, l: 70, r: 100 },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(250,250,250,1)'
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
            displaylogo: false
        };

        // Clear previous plot
        const plotDiv = document.getElementById('attention-plot');
        plotDiv.innerHTML = '';

        // Create new plot
        Plotly.newPlot('attention-plot', [trace], layout, config)
            .then(function() {
                console.log('Plot created successfully');
            })
            .catch(function(err) {
                console.error('Error creating plot:', err);
                plotDiv.innerHTML = '<p style="text-align: center; padding: 50px; color: red;">Error creating plot: ' + err.message + '</p>';
            });
    }

    function populateTable(scores) {
        const tbody = document.querySelector('#scores-table tbody');
        tbody.innerHTML = '';

        if (!scores || scores.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="4" style="text-align: center;">No scores available</td>';
            tbody.appendChild(row);
            return;
        }

        // Sort by rank score (descending) for the table
        const sortedScores = [...scores].sort((a, b) => b.rank_score - a.rank_score);

        sortedScores.forEach(function(score) {
            const row = document.createElement('tr');
            row.innerHTML =
                '<td>' + score.residue + '</td>' +
                '<td>' + score.amino_acid + '</td>' +
                '<td>' + score.raw_score.toFixed(6) + '</td>' +
                '<td>' + score.rank_score.toFixed(1) + '%</td>';
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
            window.location.href = '/api/download/csv/' + currentJobId;
        }
    });

    document.getElementById('download-pdb-raw').addEventListener('click', function() {
        if (currentJobId) {
            window.location.href = '/api/download/pdb_raw/' + currentJobId;
        }
    });

    document.getElementById('download-pdb-rank').addEventListener('click', function() {
        if (currentJobId) {
            window.location.href = '/api/download/pdb_rank/' + currentJobId;
        }
    });
});
