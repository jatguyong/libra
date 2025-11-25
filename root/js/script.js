lucide.createIcons();

/* --- UNIFIED STARFIELD ENGINE (SMOOTH TRANSITION) --- */
const canvas = document.getElementById('space-canvas');
const ctx = canvas.getContext('2d');

let width, height;
let stars = [];
const numStars = 6000; 

let speed = 0.05; 
let targetSpeed = 0.05;

const STAR_COLORS = [
    { r: 255, g: 255, b: 255 }, 
    { r: 200, g: 220, b: 255 }, 
    { r: 255, g: 240, b: 200 }, 
    { r: 255, g: 200, b: 150 }  
];

const clusters = [];
const numClusters = 8; 

function initClusters() {
    clusters.length = 0;
    for(let i=0; i<numClusters; i++) {
        clusters.push({
            x: (Math.random() - 0.5) * 4000, 
            y: (Math.random() - 0.5) * 2000, 
            z: Math.random() * 2000 + 500,   
            spread: 300 + Math.random() * 500 
        });
    }
}

function randomGaussian() {
    let u = 0, v = 0;
    while(u === 0) u = Math.random(); 
    while(v === 0) v = Math.random();
    return Math.sqrt( -2.0 * Math.log( u ) ) * Math.cos( 2.0 * Math.PI * v );
}

function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
}
window.addEventListener('resize', resize);
resize();
initClusters();

class Star {
    constructor() {
        this.reset(true);
    }

    reset(initial = false) {
        const useCluster = Math.random() < 0.7;
        
        // Spawn logic
        if (useCluster && clusters.length > 0) {
            const cluster = clusters[Math.floor(Math.random() * clusters.length)];
            this.x = cluster.x + randomGaussian() * cluster.spread;
            this.y = cluster.y + randomGaussian() * cluster.spread;
            this.z = cluster.z + randomGaussian() * (cluster.spread * 0.5);
            if (this.z < 1) this.z = Math.random() * 2000;
        } else {
            this.x = (Math.random() - 0.5) * width * 4;
            this.y = (Math.random() - 0.5) * height * 4;
            this.z = Math.random() * 3000;
        }

        if (!initial) {
            this.z = 3000; 
        }

        this.pz = this.z; 

        this.rgb = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
        this.color = `rgb(${this.rgb.r},${this.rgb.g},${this.rgb.b})`;
        
        const isPlanet = Math.random() < 0.005; 
        if (isPlanet) {
            this.size = Math.random() * 4 + 2.5; 
            this.isPlanet = true;
        } else {
            this.size = Math.pow(Math.random(), 3) * 2.5 + 0.5;
            this.isPlanet = false;
        }

        this.baseAlpha = 0.3 + Math.random() * 0.7; 
        this.blinkOffset = Math.random() * Math.PI * 2;
        this.blinkSpeed = 0.002 + Math.random() * 0.03; 
        if (Math.random() < 0.05) this.blinkSpeed = 0.1; 
        this.currentAlpha = this.baseAlpha;
    }

    update() {
        // Store previous z before update
        this.pz = this.z;
        
        // Move star
        this.z -= speed;

        // Respawn
        if (this.z < 1) {
            this.reset();
            this.pz = this.z + speed; // Prevent streak from back to front
        }

        // Opacity Logic:
        // Smoothly blend from twinkling (idle) to steady bright (warp)
        const twinkleVal = Math.sin(Date.now() * this.blinkSpeed + this.blinkOffset);
        const idleAlpha = this.baseAlpha + (twinkleVal * 0.2);
        const clampedIdle = Math.max(0, Math.min(1, idleAlpha));
        
        // Warp factor (approximate)
        const warpFactor = Math.min(1, speed / 10);
        
        if (this.isPlanet) {
            this.currentAlpha = 1;
        } else {
            // Interpolate between twinkling and full brightness based on speed
            this.currentAlpha = clampedIdle * (1 - warpFactor) + 1.0 * warpFactor;
        }
    }

    draw() {
        const x = (this.x / this.z) * width + width / 2;
        const y = (this.y / this.z) * height + height / 2;

        // Bounds check (slightly padded to allow trails to enter/exit smoothly)
        if (x < -100 || x > width + 100 || y < -100 || y > height + 100) return;

        const scale = (1 - this.z / 3000); 
        if (scale < 0) return;

        const r = this.size * scale;
        
        // Calculate previous position for trail
        const px = (this.x / this.pz) * width + width / 2;
        const py = (this.y / this.pz) * height + height / 2;
        
        ctx.beginPath();
        ctx.lineCap = 'round'; // Essential for smooth dot-to-streak transition
        
        // Color & Opacity
        const alpha = this.currentAlpha * scale;
        ctx.strokeStyle = `rgba(${this.rgb.r}, ${this.rgb.g}, ${this.rgb.b}, ${alpha})`;
        
        // Planet Trail is thinner relative to its body size
        ctx.lineWidth = this.isPlanet ? r * 0.6 : r;

        ctx.moveTo(px, py);
        ctx.lineTo(x, y);
        ctx.stroke();
        
        // Extra glow for planets/large stars (only in drawing, not part of trail logic)
        if (this.isPlanet || r > 2) {
            ctx.beginPath();
            ctx.fillStyle = `rgba(${this.rgb.r}, ${this.rgb.g}, ${this.rgb.b}, ${alpha * 0.3})`;
            ctx.arc(x, y, r * 2, 0, Math.PI * 2);
            ctx.fill();
        }
    }
}

for (let i = 0; i < numStars; i++) {
    stars.push(new Star());
}

function animate() {
    // Pure black clear
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, width, height);
    
    // Smooth speed interpolation
    speed += (targetSpeed - speed) * 0.02;
    
    stars.forEach(star => {
        star.update();
        star.draw();
    });
    requestAnimationFrame(animate);
}
animate();


/* --- LIBRA CHAT LOGIC --- */
const chatContainer = document.getElementById('chat-container');
const userInput = document.getElementById('user-input');
const actionBtn = document.getElementById('action-btn');
const iconMic = document.getElementById('icon-mic');
const iconSend = document.getElementById('icon-send');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');
const filePreview = document.getElementById('file-preview');
const fileNameSpan = document.getElementById('filename');
const emptyState = document.getElementById('empty-state');
const inputContainer = document.getElementById('input-container');

let isProcessing = false;
let isListening = false;
let hasText = false;

// Auto-resize
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
    if(this.value === '') this.style.height = 'auto';
    
    if (this.value.trim().length > 0) {
        if (!hasText) showSendIcon();
    } else {
        if (hasText) showMicIcon();
    }
});

function showSendIcon() {
    hasText = true;
    iconMic.classList.add('opacity-0', 'scale-75');
    iconSend.classList.remove('opacity-0', 'scale-75');
    actionBtn.classList.add('bg-white', 'text-black'); 
    if(isListening) toggleListening(false); 
}

function showMicIcon() {
    hasText = false;
    iconSend.classList.add('opacity-0', 'scale-75');
    iconMic.classList.remove('opacity-0', 'scale-75');
    actionBtn.classList.remove('bg-white', 'text-black'); 
}

function toggleListening(forceState) {
    const newState = forceState !== undefined ? forceState : !isListening;
    isListening = newState;

    if (isListening) {
        inputContainer.classList.add('border-red-500/50');
        userInput.placeholder = "Listening...";
        userInput.disabled = true;
        iconMic.classList.add('listening-pulse');
        actionBtn.classList.add('text-red-400');
    } else {
        inputContainer.classList.remove('border-red-500/50');
        userInput.placeholder = "Ask Libra anything...";
        userInput.disabled = false;
        userInput.focus();
        iconMic.classList.remove('listening-pulse');
        actionBtn.classList.remove('text-red-400');
    }
}

actionBtn.addEventListener('click', () => {
    if (hasText) {
        handleSend();
    } else {
        toggleListening();
    }
});

uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileNameSpan.textContent = e.target.files[0].name;
        filePreview.classList.remove('hidden');
    }
});
window.clearFile = () => {
    fileInput.value = '';
    filePreview.classList.add('hidden');
};

function handleSend() {
    const text = userInput.value.trim();
    if ((!text && fileInput.files.length === 0) || isProcessing) return;

    if (emptyState) emptyState.style.display = 'none';

    appendMessage('user', text);
    userInput.value = '';
    userInput.style.height = 'auto';
    clearFile();
    showMicIcon(); 

    isProcessing = true;
    actionBtn.disabled = true;
    targetSpeed = 80; 
    
    simulateAIResponse();
}

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
});

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `w-full flex ${role === 'user' ? 'justify-end' : 'justify-start'} msg-enter`;
    
    const avatarHtml = role === 'ai' 
        ? `<div class="w-6 h-6 mt-1 flex items-center justify-center opacity-70"><i data-lucide="scale" class="w-4 h-4 text-white"></i></div>`
        : `<div class="w-6 h-6 mt-1 flex items-center justify-center opacity-70"><div class="w-2 h-2 bg-white rounded-full"></div></div>`;

    const bubbleClass = role === 'user' 
        ? 'bg-white/10 border border-white/10 text-white' 
        : 'text-gray-300'; 

    let innerContent = '';
    if (role === 'user') {
        innerContent = `<div class="${bubbleClass} px-4 py-2 text-sm font-light tracking-wide rounded-sm">${escapeHtml(content)}</div>`;
    } else {
        innerContent = `<div class="${bubbleClass} pr-4 py-2 text-sm font-light leading-relaxed w-full">${content}</div>`;
    }

    msgDiv.innerHTML = `
        <div class="flex gap-4 max-w-3xl ${role === 'user' ? 'flex-row-reverse' : 'flex-row'}">
            ${avatarHtml}
            ${innerContent}
        </div>
    `;

    chatContainer.appendChild(msgDiv);
    scrollToBottom();
    lucide.createIcons();
    return msgDiv;
}

// --- TYPEWRITER & LOGIC ANIMATION ---

async function typeLogLine(container, text, className) {
    const line = document.createElement('div');
    line.className = className || 'text-gray-400';
    line.innerHTML = '<span class="cursor-blink"></span>';
    container.appendChild(line);
    
    const siblings = container.querySelectorAll('.cursor-blink');
    siblings.forEach(s => { if (s.parentElement !== line) s.remove(); });

    const chars = text.split('');
    let currentText = '';
    
    for (let char of chars) {
        currentText += char;
        line.innerHTML = `${currentText}<span class="cursor-blink"></span>`;
        await wait(Math.random() * 10 + 5); 
        container.scrollTop = container.scrollHeight;
    }
    return line;
}

async function appendLogText(lineElement, text, className) {
    const cursor = lineElement.querySelector('.cursor-blink');
    if(cursor) cursor.remove();

    const span = document.createElement('span');
    span.className = className || '';
    lineElement.appendChild(span);
    
    const newCursor = document.createElement('span');
    newCursor.className = 'cursor-blink';
    lineElement.appendChild(newCursor);

    const chars = text.split('');
    let currentText = '';
    
    for (let char of chars) {
        currentText += char;
        span.textContent = currentText;
        await wait(Math.random() * 10 + 5);
    }
}

async function animateProgressBar(barElement, targetWidth, duration) {
     return new Promise(resolve => {
        barElement.style.width = '0%';
        requestAnimationFrame(() => {
            barElement.style.transition = `width ${duration}ms cubic-bezier(0.25, 0.46, 0.45, 0.94)`;
            barElement.style.width = targetWidth + '%';
        });
        setTimeout(resolve, duration);
     });
}

async function simulateAIResponse() {
    const aiMsgWrapper = appendMessage('ai', '');
    const contentArea = aiMsgWrapper.querySelector('.text-gray-300');
    
    const cotId = 'cot-' + Date.now();
    
    // Visual Representations as SVGs (Restored)
    const visuals = {
        scan: `<svg viewBox="0 0 100 100" class="w-full h-full opacity-20 text-white fill-current"><rect x="10" y="10" width="80" height="80" rx="10" stroke="currentColor" stroke-width="2" fill="none"/><path d="M20 30h60M20 50h60M20 70h40" stroke="currentColor" stroke-width="2"/></svg>`,
        logic: `<svg viewBox="0 0 100 100" class="w-full h-full opacity-20 text-white fill-current"><path d="M50 20v60M20 50h60M20 20l60 60M80 20L20 80" stroke="currentColor" stroke-width="1"/></svg>`,
        graph: `<svg viewBox="0 0 100 100" class="w-full h-full opacity-20 text-white fill-current"><circle cx="50" cy="50" r="5"/><circle cx="20" cy="80" r="5"/><circle cx="80" cy="20" r="5"/><line x1="50" y1="50" x2="20" y2="80" stroke="currentColor"/><line x1="50" y1="50" x2="80" y2="20" stroke="currentColor"/></svg>`,
        chip: `<svg viewBox="0 0 100 100" class="w-full h-full opacity-20 text-white fill-current"><rect x="25" y="25" width="50" height="50" stroke="currentColor" stroke-width="2"/><path d="M25 35h-10M25 50h-10M25 65h-10M75 35h10M75 50h10M75 65h10M35 25v-10M50 25v-10M65 25v-10M35 75v10M50 75v10M65 75v10" stroke="currentColor" stroke-width="2"/></svg>`,
        shield: `<svg viewBox="0 0 100 100" class="w-full h-full opacity-20 text-white fill-current"><path d="M50 10L20 20v30c0 30 30 40 30 40s30-10 30-40V20L50 10z" stroke="currentColor" stroke-width="2" fill="none"/></svg>`
    };

    contentArea.innerHTML = `
        <div id="${cotId}-container" class="mb-4 border-l border-white/20 pl-4 py-2 bg-white/5 rounded-r w-full max-w-xl transition-all duration-700 ease-in-out relative overflow-hidden">
            
            <!-- Visual Background Overlay (Restored) -->
            <div id="${cotId}-visual-bg" class="absolute right-0 top-0 bottom-0 w-32 pointer-events-none flex items-center justify-center p-4 transition-opacity duration-500">
                ${visuals.scan}
            </div>

            <!-- Header / Current Status -->
            <div class="flex items-center gap-3 cursor-pointer group relative z-10" onclick="toggleCoT('${cotId}')">
                
                <!-- Dynamic Status Icon Container -->
                <div id="${cotId}-icon-container" class="w-5 h-5 flex items-center justify-center relative shrink-0">
                     <div class="thinking-dot"></div>
                     <div class="thinking-dot"></div>
                </div>

                <div class="flex-1 min-w-0">
                     <span class="text-[11px] font-mono text-gray-300 tracking-wider uppercase transition-colors group-hover:text-white" id="${cotId}-status">Initializing...</span>
                     <!-- Progress Bar (Yellow) -->
                     <div id="${cotId}-bar-container" class="h-0.5 bg-white/10 w-full mt-2 rounded-full overflow-hidden transition-all duration-500">
                          <div id="${cotId}-progress-fill" class="h-full bg-yellow-500/80 w-0"></div>
                     </div>
                </div>
                
                <i data-lucide="chevron-down" class="w-3 h-3 text-gray-500 ml-auto transition-transform group-hover:text-white shrink-0" id="${cotId}-arrow"></i>
            </div>
            
            <!-- Collapsible Logs -->
            <div id="${cotId}-logs" class="hidden mt-3 font-mono text-[11px] space-y-1.5 max-h-48 overflow-y-auto pr-2 border-t border-white/5 pt-2 relative z-10">
                 <!-- Animated logs appear here -->
            </div>
        </div>
        <!-- Final Text -->
        <div id="${cotId}-final" class="hidden"></div>
    `;
    
    lucide.createIcons();
    const container = document.getElementById(`${cotId}-container`);
    const logsContainer = document.getElementById(`${cotId}-logs`);
    const statusLabel = document.getElementById(`${cotId}-status`);
    const iconContainer = document.getElementById(`${cotId}-icon-container`);
    const progressFill = document.getElementById(`${cotId}-progress-fill`);
    const barContainer = document.getElementById(`${cotId}-bar-container`);
    const visualBg = document.getElementById(`${cotId}-visual-bg`);
    
    const iconTemplates = {
        scan: `<i data-lucide="scan-line" class="w-4 h-4 text-white animate-pulse"></i>`,
        translate: `<i data-lucide="binary" class="w-4 h-4 text-white"></i>`,
        graph: `<div class="relative w-full h-full"><i data-lucide="share-2" class="w-4 h-4 text-white absolute inset-0 m-auto anim-spin-slow"></i></div>`,
        inference: `<i data-lucide="cpu" class="w-4 h-4 text-white animate-pulse"></i>`,
        valid: `<i data-lucide="shield-check" class="w-4 h-4 text-white"></i>`,
        synth: `<i data-lucide="message-square-dashed" class="w-4 h-4 text-white"></i>`,
        done: `<i data-lucide="check" class="w-4 h-4 text-yellow-400"></i>`
    };

    const steps = [
        { 
            status: "PARSING INTENT", 
            log: "Vectorizing input query for semantic extraction...", 
            style: "log-secondary",
            icon: iconTemplates.scan,
            visual: visuals.scan
        },
        { 
            status: "TRANSLATING LOGIC", 
            log: "Converting natural language to First-Order Logic predicates...", 
            style: "log-primary",
            icon: iconTemplates.translate,
            visual: visuals.logic
        },
        { 
            status: "GRAPHRAG QUERY", 
            log: "Traversing Knowledge Graph edges for contextual nodes...", 
            style: "log-secondary",
            icon: iconTemplates.graph,
            visual: visuals.graph
        },
        { 
            status: "GRAPHRAG QUERY", 
            log: ">> Retrieving semantic subgraph...", 
            style: "log-dim",
            icon: iconTemplates.graph,
            visual: visuals.graph
        },
        { 
            status: "INFERENCE ENGINE", 
            log: "Executing resolution algorithm on logic gates...", 
            style: "log-primary",
            icon: iconTemplates.inference,
            visual: visuals.chip
        },
        { 
            status: "VALIDATING", 
            log: "Checking logical consistency and constraints...", 
            style: "log-secondary",
            icon: iconTemplates.valid,
            visual: visuals.shield
        },
        { 
            status: "SYNTHESIZING", 
            log: "Translating symbolic output to natural language...", 
            style: "log-primary",
            icon: iconTemplates.synth,
            visual: visuals.logic
        }
    ];

    for (const step of steps) {
        iconContainer.innerHTML = step.icon;
        visualBg.innerHTML = step.visual;
        lucide.createIcons(); 
        
        statusLabel.textContent = step.status;
        
        const lineEl = await typeLogLine(logsContainer, step.log, step.style);
        
        const duration = Math.random() * 1600 + 200;
        await animateProgressBar(progressFill, 100, duration);
        await appendLogText(lineEl, " Success.", "log-success font-bold");
        
        await wait(Math.random() * 300 + 100); 
    }

    // End Hyperspace
    targetSpeed = 0.05; 
    
    // Finalize & Shrink
    statusLabel.textContent = "LOGIC VERIFIED";
    statusLabel.className = "text-[11px] font-mono text-yellow-400 tracking-wider uppercase";
    iconContainer.innerHTML = iconTemplates.done;
    lucide.createIcons();
    
    // Shrink Container logic
    container.classList.remove('w-full', 'max-w-xl', 'bg-white/5');
    container.classList.add('w-fit', 'pr-6', 'bg-yellow-500/5', 'border-yellow-500/30');
    
    // Hide Progress Bar & Visual BG
    barContainer.style.height = '0';
    barContainer.style.opacity = '0';
    visualBg.style.opacity = '0';
    
    logsContainer.querySelectorAll('.cursor-blink').forEach(c => c.remove());

    const finalDiv = document.getElementById(`${cotId}-final`);
    finalDiv.classList.remove('hidden');
    const responseText = "The logic gate has validated the parameters. Based on the inference engine's resolution, the conclusion is structurally sound. I have prepared the requested output.";
    
    await typeWriter(finalDiv, responseText);

    isProcessing = false;
    actionBtn.disabled = false;
}

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
function scrollToBottom() { chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' }); }
function escapeHtml(text) { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }

window.toggleCoT = (id) => {
    const logs = document.getElementById(`${id}-logs`);
    const arrow = document.getElementById(`${id}-arrow`);
    
    if (logs.classList.contains('hidden')) {
        logs.classList.remove('hidden');
        arrow.classList.add('rotate-180');
        logs.scrollTop = logs.scrollHeight;
    } else {
        logs.classList.add('hidden');
        arrow.classList.remove('rotate-180');
    }
};

async function typeWriter(element, text) {
    const chars = text.split('');
    element.innerHTML = '';
    for (let i = 0; i < chars.length; i++) {
        element.innerHTML += chars[i];
        if(chars[i] === '.') await wait(200);
        else await wait(15);
        scrollToBottom();
    }
}