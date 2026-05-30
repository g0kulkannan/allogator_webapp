// AlloGator frontend

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('prediction-form');
    const sequenceInput = document.getElementById('sequence');
    const seqLengthSpan = document.getElementById('seq-length');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = submitBtn.querySelector('.btn-text');
    const btnLoading = submitBtn.querySelector('.btn-loading');
    const resultsSection = document.getElementById('results');
    const errorSection = document.getElementById('error');
    const errorText = document.getElementById('error-text');
    const modelSelect = document.getElementById('model-select');
    const modelBlurb = document.getElementById('model-blurb');
    const exampleSelect = document.getElementById('example-select');

    let currentJobId = null;
    let currentData = null;
    let models = [];

    // --- bootstrap: load models + examples --------------------------------
    fetch('/api/models').then(r => r.json()).then(data => {
        models = data.models;
        models.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.key;
            opt.textContent = m.name + (m.recommended ? '  (recommended)' : '') + ' · ' + m.params;
            if (m.key === data.default) opt.selected = true;
            modelSelect.appendChild(opt);
        });
        updateModelBlurb();
    }).catch(() => { modelBlurb.textContent = 'Could not load model list.'; });

    modelSelect.addEventListener('change', updateModelBlurb);
    function updateModelBlurb() {
        const m = models.find(x => x.key === modelSelect.value);
        modelBlurb.textContent = m ? m.blurb : '';
    }

    fetch('/api/examples').then(r => r.json()).then(data => {
        data.examples.forEach(e => {
            const opt = document.createElement('option');
            opt.value = e.id;
            opt.textContent = e.label + ' · ' + e.length + ' aa';
            exampleSelect.appendChild(opt);
        });
    }).catch(() => {});

    exampleSelect.addEventListener('change', function () {
        if (!this.value) return;
        fetch('/api/examples/' + this.value).then(r => r.json()).then(e => {
            sequenceInput.value = e.sequence;
            document.getElementById('active-residues').value = e.active_residues;
            seqLengthSpan.textContent = e.sequence.length;
        });
    });

    sequenceInput.addEventListener('input', function () {
        seqLengthSpan.textContent = this.value.replace(/\s/g, '').replace(/^>.*$/gm, '').length;
    });

    // --- submit -----------------------------------------------------------
    form.addEventListener('submit', async function (e) {
        e.preventDefault();
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';
        setLoading(true);

        try {
            const body = {
                sequence: sequenceInput.value,
                active_residues: document.getElementById('active-residues').value,
                model: modelSelect.value || undefined,
                pdb_code: document.getElementById('pdb-code').value || null
            };
            const res = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Prediction failed.');
            currentJobId = data.job_id;
            currentData = data;
            displayResults(data);
        } catch (err) {
            showError(err.message);
        } finally {
            setLoading(false);
        }
    });

    function setLoading(on) {
        submitBtn.disabled = on;
        btnText.style.display = on ? 'none' : 'inline';
        btnLoading.style.display = on ? 'inline' : 'none';
    }

    // --- results ----------------------------------------------------------
    function displayResults(data) {
        resultsSection.style.display = 'block';
        document.getElementById('run-meta').textContent =
            data.model.name + ' · ' + data.sequence_length + ' aa · active site ' +
            data.active_residues.join(', ');

        renderSummary(data);

        // PDB downloads + note
        const rankBtn = document.getElementById('download-pdb-rank');
        const rawBtn = document.getElementById('download-pdb-raw');
        rankBtn.style.display = data.has_pdb ? 'inline-block' : 'none';
        rawBtn.style.display = data.has_pdb ? 'inline-block' : 'none';
        const note = document.getElementById('pdb-note');
        if (data.pdb_error) { note.style.display = 'block'; note.textContent = data.pdb_error; }
        else { note.style.display = 'none'; }

        populateTable(data.scores);
        setTimeout(() => createPlot(data.scores, data.active_residues), 50);

        const grid = document.querySelector('.results-grid');
        if (data.has_pdb) { grid.classList.add('has-viewer'); showViewer(data); }
        else { grid.classList.remove('has-viewer'); document.getElementById('viewer-container').style.display = 'none'; }

        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function renderSummary(data) {
        const top = data.scores[0];
        const nTop = data.scores.filter(s => s.is_top).length;
        const cards = [
            { label: 'Top-ranked residue', value: top ? (top.amino_acid + top.residue) : '—',
              sub: top ? top.rank_score.toFixed(1) + 'th percentile' : '' },
            { label: 'Top-decile residues', value: nTop,
              sub: '≥ 90th percentile' },
            { label: 'Residues scored', value: data.scores.length,
              sub: 'excludes active site + neighbors' },
            { label: 'Model', value: data.model.params, sub: data.model.name }
        ];
        document.getElementById('summary-cards').innerHTML = cards.map(c =>
            '<div class="card"><div class="card-value">' + c.value + '</div>' +
            '<div class="card-label">' + c.label + '</div>' +
            '<div class="card-sub">' + c.sub + '</div></div>'
        ).join('');
    }

    // Plasma-like color stops to match the paper figures.
    const PLASMA = [
        [0.0, '#0d0887'], [0.25, '#6a00a8'], [0.5, '#b12a90'],
        [0.75, '#e16462'], [0.9, '#fca636'], [1.0, '#f0f921']
    ];

    function createPlot(scores, activeResidues) {
        const div = document.getElementById('attention-plot');
        if (!scores || !scores.length) { div.innerHTML = '<p class="muted">No scores to plot.</p>'; return; }
        if (typeof Plotly === 'undefined') { div.innerHTML = '<p class="muted">Plot library unavailable.</p>'; return; }

        const byPos = [...scores].sort((a, b) => a.residue - b.residue);
        const trace = {
            x: byPos.map(s => s.residue),
            y: byPos.map(s => s.rank_score),
            type: 'scatter', mode: 'markers',
            marker: {
                size: byPos.map(s => s.is_top ? 9 : 6),
                color: byPos.map(s => s.rank_score),
                colorscale: PLASMA, cmin: 0, cmax: 100,
                showscale: true,
                colorbar: { title: { text: 'Rank %', side: 'right' }, thickness: 14 },
                line: { width: byPos.map(s => s.is_top ? 1.2 : 0), color: '#222' }
            },
            text: byPos.map(s => s.amino_acid + s.residue + '<br>rank ' + s.rank_score.toFixed(1) + '%'),
            hoverinfo: 'text'
        };
        const layout = {
            margin: { t: 10, b: 50, l: 55, r: 90 },
            xaxis: { title: 'Residue number', gridcolor: '#eee', zeroline: false },
            yaxis: { title: 'Attention rank percentile', range: [0, 100], gridcolor: '#eee', zeroline: false },
            shapes: [{ type: 'line', x0: byPos[0].residue, x1: byPos[byPos.length - 1].residue,
                       y0: 90, y1: 90, line: { color: '#aaa', width: 1, dash: 'dot' } }],
            paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: '#fafafa'
        };
        Plotly.newPlot('attention-plot', [trace], layout,
            { responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] });
    }

    function populateTable(scores) {
        const tbody = document.querySelector('#scores-table tbody');
        tbody.innerHTML = '';
        scores.forEach((s, i) => {
            const tr = document.createElement('tr');
            if (s.is_top) tr.className = 'top-row';
            tr.innerHTML =
                '<td>' + (i + 1) + '</td>' +
                '<td>' + s.residue + '</td>' +
                '<td>' + s.amino_acid + '</td>' +
                '<td><div class="bar-cell"><span class="bar" style="width:' + s.rank_score + '%"></span>' +
                    '<span class="bar-num">' + s.rank_score.toFixed(1) + '</span></div></td>' +
                '<td>' + s.raw_score.toFixed(5) + '</td>';
            tbody.appendChild(tr);
        });
    }

    document.getElementById('table-filter').addEventListener('input', function () {
        const q = this.value.trim().toLowerCase();
        document.querySelectorAll('#scores-table tbody tr').forEach(tr => {
            tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
    });

    // --- 3D viewer --------------------------------------------------------
    function showViewer(data) {
        const container = document.getElementById('viewer-container');
        container.style.display = 'block';
        const el = document.getElementById('mol-viewer');
        el.innerHTML = '';
        if (typeof $3Dmol === 'undefined') { container.style.display = 'none'; return; }

        fetch('/api/download/pdb_rank/' + data.job_id).then(r => r.text()).then(pdb => {
            const viewer = $3Dmol.createViewer(el, { backgroundColor: 'white' });
            viewer.addModel(pdb, 'pdb');
            // Color cartoon by B-factor (= rank percentile) on a plasma-like gradient.
            viewer.setStyle({}, { cartoon: { colorscheme: {
                prop: 'b',
                gradient: 'roygb',
                min: 0, max: 100
            } } });
            // Mark active-site residues as red sticks.
            (data.active_residues || []).forEach(r => {
                viewer.setStyle({ resi: r }, { stick: { color: 'red' }, cartoon: { color: 'red' } });
            });
            viewer.zoomTo();
            viewer.render();
        }).catch(() => { container.style.display = 'none'; });
    }

    // --- downloads --------------------------------------------------------
    function dl(path) { if (currentJobId) window.location.href = path + currentJobId; }
    document.getElementById('download-csv').addEventListener('click', () => dl('/api/download/csv/'));
    document.getElementById('download-json').addEventListener('click', () => dl('/api/download/json/'));
    document.getElementById('download-fasta').addEventListener('click', () => dl('/api/download/fasta/'));
    document.getElementById('download-pdb-rank').addEventListener('click', () => dl('/api/download/pdb_rank/'));
    document.getElementById('download-pdb-raw').addEventListener('click', () => dl('/api/download/pdb_raw/'));

    function showError(msg) {
        errorText.textContent = msg;
        errorSection.style.display = 'block';
        errorSection.scrollIntoView({ behavior: 'smooth' });
    }
});
