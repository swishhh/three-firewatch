import { loadCss } from '../../tools/files/cssLoader.js';
import { addUpdateCallback } from '../../registry/update.js';
import { onSelectChange } from './mouse/select.js';

const DEG = Math.PI / 180;

class SelectionPanel {
    constructor() {
        this.object = null;
        this.panel = null;
        this._drag = null;
        this._scrubbers = [];
    }

    init() {
        loadCss('./css/selection-panel.css', () => {
            this._buildPanel();
            this._initGlobalDrag();
            this._startUpdateLoop();
            onSelectChange((object) => this.setObject(object));
        });
    }

    _buildPanel() {
        this.panel = document.createElement('div');
        this.panel.className = 'sp';
        this.panel.innerHTML = `
            <div class="sp-header">
                <span class="sp-title">—</span>
                <button class="sp-close">✕</button>
            </div>
            <div class="sp-section" id="sp-position">
                <div class="sp-section-label">Position <span class="sp-hint">drag ←→</span></div>
            </div>
            <div class="sp-section" id="sp-rotation">
                <div class="sp-section-label">Rotation <span class="sp-hint">drag ←→</span></div>
            </div>
            <div class="sp-section" id="sp-scale">
                <div class="sp-section-label">Scale <span class="sp-hint">drag ←→  [1–5]</span></div>
            </div>
            <div class="sp-section">
                <div class="sp-section-label">Children <span class="sp-children-count"></span></div>
                <div class="sp-children-list"></div>
            </div>
        `;

        this.panel.querySelector('.sp-close').addEventListener('click', () => {
            this.setObject(null);
        });

        const posSection = this.panel.querySelector('#sp-position');
        ['x', 'y', 'z'].forEach(axis => {
            posSection.appendChild(this._makeRow(axis.toUpperCase(), {
                sensitivity: 0.05,
                getValue: () => this.object ? this.object.position[axis] : 0,
                setValue: (v) => { if (this.object) this.object.position[axis] = v; },
                format: v => v.toFixed(2),
            }));
        });

        const rotSection = this.panel.querySelector('#sp-rotation');
        ['x', 'y', 'z'].forEach(axis => {
            rotSection.appendChild(this._makeRow(axis.toUpperCase(), {
                sensitivity: 0.5,
                getValue: () => this.object ? this.object.rotation[axis] / DEG : 0,
                setValue: (v) => { if (this.object) this.object.rotation[axis] = v * DEG; },
                format: v => v.toFixed(1) + '°',
            }));
        });

        const scaleSection = this.panel.querySelector('#sp-scale');
        scaleSection.appendChild(this._makeRow('S', {
            sensitivity: 0.005,
            min: 0,
            max: 5,
            getValue: () => this.object ? this.object.scale.x : 1,
            setValue: (v) => { if (this.object) this.object.scale.setScalar(v); },
            format: v => v.toFixed(3),
        }));

        document.body.appendChild(this.panel);
        this.panel.style.display = 'none';
    }

    _makeRow(axisLabel, { sensitivity, min, max, getValue, setValue, format }) {
        const row = document.createElement('div');
        row.className = 'sp-row';

        const axis = document.createElement('span');
        axis.className = 'sp-axis';
        axis.textContent = axisLabel;

        const scrubber = document.createElement('div');
        scrubber.className = 'sp-scrubber';

        const valueSpan = document.createElement('span');
        valueSpan.className = 'sp-scrubber-value';
        valueSpan.textContent = '—';
        scrubber.appendChild(valueSpan);

        scrubber.addEventListener('mousedown', (e) => {
            if (!this.object) return;
            this._drag = { sensitivity, min, max, setValue, startX: e.clientX, startVal: getValue() };
            document.body.style.cursor = 'ew-resize';
            e.preventDefault();
        });

        this._scrubbers.push({ el: valueSpan, getValue, format });

        row.appendChild(axis);
        row.appendChild(scrubber);
        return row;
    }

    _initGlobalDrag() {
        window.addEventListener('mousemove', (e) => {
            if (!this._drag || !this.object) return;
            const { sensitivity, min, max, setValue, startX, startVal } = this._drag;
            let next = startVal + (e.clientX - startX) * sensitivity;
            if (min !== undefined) next = Math.max(min, next);
            if (max !== undefined) next = Math.min(max, next);
            setValue(next);
        });

        window.addEventListener('mouseup', () => {
            if (!this._drag) return;
            this._drag = null;
            document.body.style.cursor = '';
        });
    }

    _startUpdateLoop() {
        addUpdateCallback(() => {
            if (!this.object || !this.panel || this.panel.style.display === 'none') return;
            this._syncValues();
        });
    }

    _syncValues() {
        this._scrubbers.forEach(({ el, getValue, format }) => {
            el.textContent = format(getValue());
        });
    }

    _renderChildren() {
        const list = this.panel.querySelector('.sp-children-list');
        const countEl = this.panel.querySelector('.sp-children-count');
        list.innerHTML = '';

        const children = this.object ? this.object.children : [];
        countEl.textContent = children.length ? `(${children.length})` : '';

        if (!children.length) {
            list.innerHTML = '<span class="sp-empty">none</span>';
            return;
        }

        children.forEach(child => {
            const row = document.createElement('div');
            row.className = 'sp-child-row';
            row.textContent = `▸ ${child.name || child.type}`;
            row.title = child.uuid;
            list.appendChild(row);
        });
    }

    setObject(object) {
        this.object = object;
        if (!this.panel) return;

        if (!object) {
            this.panel.style.display = 'none';
            return;
        }

        this.panel.querySelector('.sp-title').textContent = object.name || object.type;
        this._syncValues();
        this._renderChildren();
        this.panel.style.display = 'block';
    }
}

const draw = (scene, camera, renderer) => {
    new SelectionPanel().init();
}

export { draw }
