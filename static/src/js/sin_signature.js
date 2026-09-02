/** @odoo-module */
/**
 * SinSignatureWidget — Firmador electrónico OWL para Odoo 19.
 *
 * Permite firmar dibujando sobre un canvas, subiendo una imagen (firma
 * escaneada), o capturando el nombre escrito en un estilo de tipografía
 * de firma. Emula el comportamiento del módulo Sign de Odoo.
 *
 * Se usa como widget de campo: widget="sin_signature" sobre un campo Binary,
 * por ejemplo client_signature o company_signature.
 */
import { Component, useState, onMounted, useRef, useExternalListener } from "@odoo/owl";
import { registry } from "@web/core/registry";

export class SinSignatureWidget extends Component {
    static template = "l10n_bo_contracts.SinSignatureWidget";
    static props = {
        record: Object,
        name: String,
        value: { type: [String, Object], optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        // this.props.value normalmente trae el base64 del Binary en el backend.
        this.state = useState({
            mode: "draw", // draw | upload | typed
            data: this.props.value || null,
            name: "",
            drawData: null,
        });
        this.canvasRef = useRef("canvas");
        this._drawing = false;
        this._last = { x: 0, y: 0 };
        onMounted(() => this._initCanvas());
        useExternalListener(window, "resize", () => this.refreshCanvas());
    }

    get signInstruction() {
        // Si el registro tiene un campo de instrucciones, úsalo; si no, genérico.
        const instr = this.props.record && this.props.record.data
            ? this.props.record.data.sign_instruction : null;
        return instr || "Firme aquí";
    }

    _initCanvas() {
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        // Escala para que coincida el dibujo con la resolución almacenada.
        const rect = canvas.getBoundingClientRect();
        this._scaleX = canvas.width / rect.width;
        this._scaleY = canvas.height / rect.height;
    }

    refreshCanvas() {
        // Redibuja la imagen base64 si existe tras redimensionar.
        if (this.state.data && this.state.mode === "draw") {
            const img = new Image();
            img.onload = () => this._drawImage(img);
            img.src = `data:image/png;base64,${this.state.data}`;
        }
    }

    _ctx() {
        const canvas = this.canvasRef.el;
        return canvas ? canvas.getContext("2d") : null;
    }

    _drawImage(img) {
        const ctx = this._ctx();
        if (!ctx) return;
        ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        ctx.drawImage(img, 0, 0, ctx.canvas.width, ctx.canvas.height);
    }

    _getPos(ev) {
        const rect = this.canvasRef.el.getBoundingClientRect();
        const clientX = ev.touches ? ev.touches[0].clientX : ev.clientX;
        const clientY = ev.touches ? ev.touches[0].clientY : ev.clientY;
        return {
            x: (clientX - rect.left) * this._scaleX,
            y: (clientY - rect.top) * this._scaleY,
        };
    }

    onPointerDown(ev) {
        if (this.props.readonly || this.state.mode !== "draw") return;
        this._drawing = true;
        this._last = this._getPos(ev);
    }

    onPointerMove(ev) {
        if (!this._drawing || this.props.readonly || this.state.mode !== "draw") return;
        const ctx = this._ctx();
        if (!ctx) return;
        const pos = this._getPos(ev);
        ctx.lineWidth = 2.5;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.strokeStyle = "#1a1a1a";
        ctx.beginPath();
        ctx.moveTo(this._last.x, this._last.y);
        ctx.lineTo(pos.x, pos.y);
        ctx.stroke();
        this._last = pos;
        this._emit();
    }

    onPointerUp() {
        this._drawing = false;
    }

    _emit() {
        // Exporta el canvas a un dataURL base64 y lo guarda en el campo.
        const canvas = this.canvasRef.el;
        if (!canvas) return;
        const data = canvas.toDataURL("image/png").split(",")[1];
        this.state.data = data;
        this.updateRecord(data);
    }

    updateRecord(base64) {
        if (!this.props.record || !this.props.name) return;
        this.props.record.update({ [this.props.name]: base64 });
    }

    switchMode(mode) {
        if (this.props.readonly) return;
        this.state.mode = mode;
        if (mode === "draw") {
            // Re-dibuja la firma existente en el canvas
            if (this.state.data) {
                const img = new Image();
                img.onload = () => this._drawImage(img);
                img.src = `data:image/png;base64,${this.state.data}`;
            }
        }
        if (mode === "upload") {
            this.state.data = null;
            this.updateRecord(null);
        }
    }

    onNameChange() {
        // Genera una 'firma' a partir del nombre escrito usando una fuente caligráfica.
        const name = (this.state.name || "").trim();
        if (!name) return;
        const canvas = this.canvasRef.el;
        const ctx = this._ctx();
        if (!canvas || !ctx) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = "italic 48px 'Segoe Script', 'Brush Script MT', cursive";
        ctx.fillStyle = "#1a1a1a";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(name, canvas.width / 2, canvas.height / 2);
        this.state.mode = "typed";
        this._emit();
    }

    onFileChange(ev) {
        if (this.props.readonly) return;
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result;
            const base64 = dataUrl.split(",")[1];
            this.state.data = base64;
            this.updateRecord(base64);
        };
        reader.readAsDataURL(file);
    }

    clear() {
        if (this.props.readonly) return;
        const ctx = this._ctx();
        if (ctx) ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
        this.state.data = null;
        this.updateRecord(null);
    }
}

registry.category("fields").add("sin_signature", SinSignatureWidget);
