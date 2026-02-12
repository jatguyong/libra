// Initialize Lucide icons
if (window.lucide) {
    window.lucide.createIcons();
}

/* --- CLUSTERED STARFIELD ENGINE --- */
const canvas = document.getElementById('space-canvas');
const ctx = canvas.getContext('2d');

let width, height;
let stars = [];
const numStars = 6000;
let speed = 0.05;
let targetSpeed = 0.05;

const STAR_COLORS = [
    { r: 255, g: 255, b: 255 }, { r: 200, g: 220, b: 255 },
    { r: 255, g: 240, b: 200 }, { r: 255, g: 200, b: 150 }
];

const clusters = [];
const numClusters = 8;

function initClusters() {
    clusters.length = 0;
    for (let i = 0; i < numClusters; i++) {
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
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
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
    constructor() { this.reset(true); }
    reset(initial = false) {
        const useCluster = Math.random() < 0.7;
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
        if (!initial) this.z = 3000;
        this.pz = this.z;
        this.rgb = STAR_COLORS[Math.floor(Math.random() * STAR_COLORS.length)];
        this.color = `rgb(${this.rgb.r},${this.rgb.g},${this.rgb.b})`;
        const isPlanet = Math.random() < 0.005;
        if (isPlanet) { this.size = Math.random() * 4 + 2.5; this.isPlanet = true; }
        else { this.size = Math.pow(Math.random(), 3) * 2.5 + 0.5; this.isPlanet = false; }
        this.baseAlpha = 0.3 + Math.random() * 0.7;
        this.blinkOffset = Math.random() * Math.PI * 2;
        this.blinkSpeed = 0.002 + Math.random() * 0.03;
        if (Math.random() < 0.05) this.blinkSpeed = 0.1;
        this.currentAlpha = this.baseAlpha;
    }
    update() {
        this.pz = this.z;
        this.z -= speed;
        if (this.z < 1) { this.reset(); this.pz = this.z + speed; }
        if (speed < 1) {
            if (this.isPlanet) { this.currentAlpha = 1; }
            else {
                const val = Math.sin(Date.now() * this.blinkSpeed + this.blinkOffset);
                this.currentAlpha = this.baseAlpha + (val * 0.2);
                if (this.currentAlpha < 0) this.currentAlpha = 0;
                if (this.currentAlpha > 1) this.currentAlpha = 1;
            }
        } else { this.currentAlpha = 1; }
    }
    draw() {
        const x = (this.x / this.z) * width + width / 2;
        const y = (this.y / this.z) * height + height / 2;
        if (x < -100 || x > width + 100 || y < -100 || y > height + 100) return;
        const scale = (1 - this.z / 3000);
        if (scale < 0) return;
        const r = this.size * scale;
        ctx.beginPath();
        if (speed > 1) {
            const prevX = (this.x / this.pz) * width + width / 2;
            const prevY = (this.y / this.pz) * height + height / 2;
            ctx.strokeStyle = `rgba(${this.rgb.r}, ${this.rgb.g}, ${this.rgb.b}, ${this.currentAlpha * scale})`;
            ctx.lineWidth = this.isPlanet ? r * 0.5 : r;
            ctx.moveTo(prevX, prevY); ctx.lineTo(x, y); ctx.stroke();
        } else {
            ctx.fillStyle = this.color; ctx.globalAlpha = this.currentAlpha;
            ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
            if (r > 1.5) { ctx.globalAlpha = 0.1; ctx.arc(x, y, r * 3, 0, Math.PI * 2); ctx.fill(); }
            ctx.globalAlpha = 1.0;
        }
    }
}
for (let i = 0; i < numStars; i++) stars.push(new Star());
function animate() {
    ctx.fillStyle = '#000000'; ctx.fillRect(0, 0, width, height);
    speed += (targetSpeed - speed) * 0.02;
    stars.forEach(star => { star.update(); star.draw(); });
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

// Configuration
const logicToggleBtn = document.getElementById('logic-toggle-btn');
const logicMenu = document.getElementById('logic-menu');
const currentModeIcon = document.getElementById('current-mode-icon');
const masterSwitch = document.getElementById('master-switch');
const switchThumb = document.getElementById('switch-thumb');
const ragOptions = document.getElementById('rag-options');

// State
let isInferenceEnabled = localStorage.getItem('isInferenceEnabled') === 'true';
let currentRagMode = localStorage.getItem('currentRagMode') || 'none';
let hasText = false;

// Auto-resize & Icon Toggle
userInput.addEventListener('input', function () {
    this.style.height = 'auto'; this.style.height = (this.scrollHeight) + 'px';
    if (this.value === '') this.style.height = 'auto';

    if (this.value.trim().length > 0) {
        if (!hasText) showSendIcon();
    } else {
        if (hasText) showMicIcon();
    }
});

// Dropdown Logic
if (logicToggleBtn) {
    logicToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        logicMenu.classList.toggle('hidden');
        logicMenu.classList.toggle('enter-dropdown');
    });
    document.addEventListener('click', (e) => {
        if (!logicToggleBtn.contains(e.target) && !logicMenu.contains(e.target)) {
            logicMenu.classList.add('hidden');
            logicMenu.classList.remove('enter-dropdown');
        }
    });
}

window.toggleInferenceEngine = () => {
    isInferenceEnabled = !isInferenceEnabled;
    localStorage.setItem('isInferenceEnabled', isInferenceEnabled);
    updateUIState();
};

window.selectRagMode = (mode) => {
    currentRagMode = mode;
    localStorage.setItem('currentRagMode', currentRagMode);
    document.querySelectorAll('.check-icon').forEach(el => el.classList.add('opacity-0'));
    document.getElementById(`check-${mode}`).classList.remove('opacity-0');
    // Note: Update logic normally changes icon, but now everything is omega.svg, so visual change minimal
};

function updateUIState() {
    if (isInferenceEnabled) {
        masterSwitch.classList.add('bg-white'); masterSwitch.classList.remove('bg-white/10');
        switchThumb.classList.add('translate-x-4', 'bg-black'); switchThumb.classList.remove('bg-white');
        ragOptions.classList.remove('hidden'); ragOptions.classList.add('block');
        if (currentRagMode === '') selectRagMode('none');
    } else {
        masterSwitch.classList.remove('bg-white'); masterSwitch.classList.add('bg-white/10');
        switchThumb.classList.remove('translate-x-4', 'bg-black'); switchThumb.classList.add('bg-white');
        ragOptions.classList.add('hidden'); ragOptions.classList.remove('block');
    }
    // Icons are always omega.svg now, so no need to swap data-lucide attributes
}

window.addEventListener('DOMContentLoaded', () => {
    updateUIState();
    if (isInferenceEnabled && currentRagMode !== 'none') {
        const checkEl = document.getElementById(`check-${currentRagMode}`);
        if (checkEl) checkEl.classList.remove('opacity-0');
    } else {
        const noneCheck = document.getElementById('check-none');
        if (noneCheck) noneCheck.classList.remove('opacity-0');
    }
});

window.triggerResponseAnimation = (text) => {
    if (isInferenceEnabled) {
        simulateAIResponse(text);
    } else {
        simulateDirectResponse(text);
    }
};

function showSendIcon() {
    hasText = true;
    iconMic.classList.add('opacity-0', 'scale-75'); iconSend.classList.remove('opacity-0', 'scale-75');
    actionBtn.classList.add('bg-white', 'text-black');
}

function showMicIcon() {
    hasText = false;
    iconSend.classList.add('opacity-0', 'scale-75'); iconMic.classList.remove('opacity-0', 'scale-75');
    actionBtn.classList.remove('bg-white', 'text-black');
}

// Enter Key Logic: Trigger AJAX Send
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (hasText) {
            handleChatSubmit();
        }
    }
});

actionBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (hasText) {
        handleChatSubmit();
    }
});

async function handleChatSubmit() {
    const text = userInput.value;
    if (!text.trim()) return;

    if (checkForSlashCommands(text)) {
        userInput.value = '';
        return;
    }

    // 1. UI Updates (Immediate)
    if (emptyState) emptyState.style.display = 'none';
    userInput.value = '';
    userInput.style.height = 'auto';
    showMicIcon();
    appendMessage('user', text);

    // 2. Create placeholder for AI response
    const aiMsgWrapper = appendMessage('ai', '');
    const contentArea = aiMsgWrapper.querySelector('.text-gray-300');
    contentArea.innerHTML = '<span class="animate-pulse">Thinking...</span>';

    // 3. Simple Fetch
    try {
        console.log("Sending request to /chat with:", text);
        const responsePromise = fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: text })
        }).then(r => r.json());

        // Trigger the "Thinking" UI (CoT style) if enabled, or direct
        if (isInferenceEnabled) {
            simulateAIResponse(responsePromise);
        } else {
            // Direct mode: Wait for promise then show
            const data = await responsePromise;
            contentArea.innerHTML = '';
            if (data.error) {
                contentArea.textContent = "Error: " + data.error;
                contentArea.classList.add('text-red-400');
            } else {
                await typeWriter(contentArea, data.response);
            }
        }

    } catch (e) {
        console.error("Fetch Error:", e);
        contentArea.textContent = "Error connecting to server: " + e.message;
        contentArea.classList.add('text-red-400');
    }
}

uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        fileNameSpan.textContent = e.target.files[0].name;
        filePreview.classList.remove('hidden');
    }
});
window.clearFile = () => { fileInput.value = ''; filePreview.classList.add('hidden'); };


// --- OFFLINE SEND LOGIC ---
function handleOfflineSend() {
    const text = userInput.value;
    if (!text.trim()) return;

    if (emptyState) emptyState.style.display = 'none'; // Hide welcome

    // Append user message
    appendMessage('user', text);

    // Clear input
    userInput.value = '';
    userInput.style.height = 'auto';
    showMicIcon();

    // Trigger AI response (Fake)
    if (isInferenceEnabled) {
        simulateAIResponse("The Del Campo-Cruz-Guyong (DCCG) algorithm is a method used for solving the inverse kinematics problem in robotics, specifically for redundant manipulators. It focuses on finding the joint angles of a robot arm needed to achieve a desired end-effector pose (position and orientation) while considering the robot's joint limits and potentially optimizing other criteria. Here's a breakdown of the algorithm's key aspects: 1. Problem Statement: The core problem is to determine the joint variables (angles) given a desired Cartesian pose of the robot's end-effector. For redundant robots (those with more degrees of freedom than necessary to achieve a given pose), there are infinitely many solutions. 2. Jacobian Matrix: The algorithm relies heavily on the Jacobian matrix, which maps joint velocities to end-effector velocities. The Jacobian is a matrix of partial derivatives that relates changes in joint angles to changes in end-effector position and orientation. I regret to say that I am unable to find any published works or widely recognized scientific literature explicitly detailing an algorithm named 'Del Campo-Cruz-Guyong' (DCCG) in the context of robotics or inverse kinematics. It is possible that this is a specific, unpublished algorithm, a locally used method, or perhaps the name is slightly different in the literature. If you have more information about the context in which you encountered this algorithm name, I might be able to provide a more specific answer. For example, knowing the specific robot or application area could help narrow down the search.");
    } else {
        simulateDirectResponse("The Del Campo-Cruz-Guyong (DCCG) algorithm is a method used for solving the inverse kinematics problem in robotics, specifically for redundant manipulators. It focuses on finding the joint angles of a robot arm needed to achieve a desired end-effector pose (position and orientation) while considering the robot's joint limits and potentially optimizing other criteria. Here's a breakdown of the algorithm's key aspects: 1. Problem Statement: The core problem is to determine the joint variables (angles) given a desired Cartesian pose of the robot's end-effector. For redundant robots (those with more degrees of freedom than necessary to achieve a given pose), there are infinitely many solutions. 2. Jacobian Matrix: The algorithm relies heavily on the Jacobian matrix, which maps joint velocities to end-effector velocities. The Jacobian is a matrix of partial derivatives that relates changes in joint angles to changes in end-effector position and orientation. I regret to say that I am unable to find any published works or widely recognized scientific literature explicitly detailing an algorithm named 'Del Campo-Cruz-Guyong' (DCCG) in the context of robotics or inverse kinematics. It is possible that this is a specific, unpublished algorithm, a locally used method, or perhaps the name is slightly different in the literature. If you have more information about the context in which you encountered this algorithm name, I might be able to provide a more specific answer. For example, knowing the specific robot or application area could help narrow down the search.");
    }
}

// FORMATTER
function formatText(text) {
    let formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong class="text-white font-bold">$1</strong>');
    return formatted;
}

function appendMessage(role, content) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `w-full flex ${role === 'user' ? 'justify-end' : 'justify-start'} msg-enter`;

    // REPLACE ICONS WITH LUCIDE
    const avatarHtml = role === 'ai'
        ? `<div class="w-6 h-6 mt-2 flex items-center justify-center opacity-70"><i data-lucide="omega" class="w-4 h-4 text-white"></i></div>`
        : `<div class="w-6 h-6 mt-1 flex items-center justify-center opacity-70"><div class="w-2 h-2 bg-white rounded-full"></div></div>`;

    const bubbleClass = role === 'user' ? 'bg-white/10 border border-white/10 text-white' : 'text-gray-300';
    const formattedContent = formatText(content);
    const innerContent = role === 'user'
        ? `<div class="${bubbleClass} px-4 py-2 text-sm font-light tracking-wide rounded-sm">${formattedContent}</div>`
        : `<div class="${bubbleClass} pr-4 py-2 text-sm font-light leading-relaxed w-full">${formattedContent}</div>`;

    msgDiv.innerHTML = `<div class="flex gap-4 max-w-3xl ${role === 'user' ? 'flex-row-reverse' : 'flex-row'}">${avatarHtml}${innerContent}</div>`;
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    if (window.lucide) window.lucide.createIcons();
    return msgDiv;
}

// Visual helpers
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
    const cursor = lineElement.querySelector('.cursor-blink'); if (cursor) cursor.remove();
    const span = document.createElement('span'); span.className = className || ''; lineElement.appendChild(span);
    const newCursor = document.createElement('span'); newCursor.className = 'cursor-blink'; lineElement.appendChild(newCursor);
    const chars = text.split('');
    let currentText = '';
    for (let char of chars) {
        currentText += char; span.textContent = currentText;
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

// Mode 1: Direct Response
async function simulateDirectResponse(responseText) {
    const aiMsgWrapper = appendMessage('ai', '');
    const contentArea = aiMsgWrapper.querySelector('.text-gray-300');
    const cotId = 'direct-' + Date.now();
    contentArea.innerHTML = `<div id="${cotId}-final"></div>`;
    const finalDiv = document.getElementById(`${cotId}-final`);
    const finalResponse = responseText || "System response ready.";
    await typeWriter(finalDiv, finalResponse);
    targetSpeed = 0.05;
}

// Mode 2: Chain of Thought
async function simulateAIResponse(responsePromiseOrText) {
    const aiMsgWrapper = appendMessage('ai', '');
    const contentArea = aiMsgWrapper.querySelector('.text-gray-300');
    const cotId = 'cot-' + Date.now();

    // REPLACE ICONS WITH LUCIDE
    const iconTemplates = {
        scan: `<i data-lucide="scan" class="w-4 h-4 opacity-70 animate-pulse"></i>`,
        translate: `<i data-lucide="languages" class="w-4 h-4 opacity-70"></i>`,
        graph: `<div class="relative w-full h-full"><i data-lucide="network" class="w-4 h-4 opacity-70 absolute inset-0 m-auto anim-spin-slow"></i></div>`,
        inference: `<i data-lucide="brain-circuit" class="w-4 h-4 opacity-70 animate-pulse"></i>`,
        valid: `<i data-lucide="check-circle" class="w-4 h-4 opacity-70"></i>`,
        synth: `<i data-lucide="file-text" class="w-4 h-4 opacity-70"></i>`,
        done: `<i data-lucide="check" class="w-4 h-4 opacity-100"></i>`
    };

    contentArea.innerHTML = `
        <div id="${cotId}-container" class="mb-4 border-l border-white/20 pl-4 py-2 bg-white/5 rounded-r w-full max-w-xl transition-all duration-700 ease-in-out relative overflow-hidden">
            <div class="flex items-center gap-3 cursor-pointer group relative z-10" onclick="toggleCoT('${cotId}')">
                <div id="${cotId}-icon-container" class="w-5 h-5 flex items-center justify-center relative shrink-0">
                        <div class="thinking-dot"></div><div class="thinking-dot"></div>
                </div>
                <div class="flex-1 min-w-0">
                        <span class="text-[11px] font-mono text-gray-300 tracking-wider uppercase transition-colors group-hover:text-white" id="${cotId}-status">Initializing...</span>
                        <div id="${cotId}-bar-container" class="h-0.5 bg-white/10 w-full mt-2 rounded-full overflow-hidden transition-all duration-500">
                            <div id="${cotId}-progress-fill" class="h-full bg-yellow-500/80 w-0"></div>
                        </div>
                </div>
                <!-- OMEGA ICON ARROW REPLACEMENT -->
                <img src="static/omega.svg" class="w-3 h-3 opacity-50 ml-auto transition-transform group-hover:opacity-100 shrink-0" id="${cotId}-arrow">
            </div>
            <div id="${cotId}-logs" class="hidden mt-3 font-mono text-[11px] space-y-1.5 max-h-48 overflow-y-auto pr-2 border-t border-white/5 pt-2 relative z-10"></div>
        </div>
        <div id="${cotId}-final" class="hidden"></div>
    `;

    const container = document.getElementById(`${cotId}-container`);
    const logsContainer = document.getElementById(`${cotId}-logs`);
    const statusLabel = document.getElementById(`${cotId}-status`);
    const iconContainer = document.getElementById(`${cotId}-icon-container`);
    const progressFill = document.getElementById(`${cotId}-progress-fill`);
    const barContainer = document.getElementById(`${cotId}-bar-container`);

    // --- ANIMATION SEQUENCE ---
    // We run the animation steps. If the API returns early, we might want to speed up?
    // For now, let's just run them safely. If they fail, we catch and show text.

    let responseText = "Analysis complete.";
    let errorOccurred = false;

    try {
        const steps = [
            { status: "PARSING INTENT", log: "Vectorizing input query...", style: "log-secondary", icon: iconTemplates.scan },
            { status: "TRANSLATING LOGIC", log: "Converting to FOL predicates...", style: "log-primary", icon: iconTemplates.translate },
            { status: "INFERENCE ENGINE", log: "Executing resolution algorithm...", style: "log-primary", icon: iconTemplates.inference },
            // We can reduce steps if it feels too long, but let's keep it for now.
        ];

        // Start fetching data in background variable if it's a promise
        const dataPromise = (responsePromiseOrText instanceof Promise) ? responsePromiseOrText : Promise.resolve(responsePromiseOrText);

        for (const step of steps) {
            iconContainer.innerHTML = step.icon;
            if (window.lucide) window.lucide.createIcons();
            statusLabel.textContent = step.status;

            // Run animation steps
            const lineEl = await typeLogLine(logsContainer, step.log, step.style);
            await animateProgressBar(progressFill, 100, Math.random() * 500 + 200); // Speed up slightly
            await appendLogText(lineEl, " Success.", "log-success font-bold");

            // Check if we already have the data? 
            // Optional optimization: if data is ready, break loop? 
            // Let's just finish the animation to look cool.
        }

        statusLabel.textContent = "SYNTHESIZING OUTPUT";
        iconContainer.innerHTML = iconTemplates.synth;
        if (window.lucide) window.lucide.createIcons();

        // NOW we await the data
        const result = await dataPromise;

        if (typeof result === 'object' && result.response) {
            responseText = result.response;
        } else if (typeof result === 'string') {
            responseText = result;
        } else if (result.error) {
            throw new Error(result.error);
        } else {
            responseText = JSON.stringify(result);
        }

    } catch (e) {
        console.error("Animation/Fetch Error:", e);
        errorOccurred = true;
        responseText = "Error: " + (e.message || "Unknown error occurred.");
    }

    // --- FINALIZE ---
    targetSpeed = 0.05;
    statusLabel.textContent = errorOccurred ? "SYSTEM ERROR" : "LOGIC VERIFIED";
    statusLabel.className = errorOccurred ? "text-[11px] font-mono text-red-400 tracking-wider uppercase" : "text-[11px] font-mono text-yellow-400 tracking-wider uppercase";
    iconContainer.innerHTML = errorOccurred ? `<i data-lucide="alert-triangle" class="w-4 h-4 text-red-400"></i>` : iconTemplates.done;
    if (window.lucide) window.lucide.createIcons();

    container.classList.remove('w-full', 'max-w-xl', 'bg-white/5');
    container.classList.add('w-fit', 'pr-6', errorOccurred ? 'bg-red-500/5' : 'bg-yellow-500/5', errorOccurred ? 'border-red-500/30' : 'border-yellow-500/30');
    barContainer.style.height = '0'; barContainer.style.opacity = '0';
    logsContainer.querySelectorAll('.cursor-blink').forEach(c => c.remove());

    const finalDiv = document.getElementById(`${cotId}-final`);
    finalDiv.classList.remove('hidden');

    // Safety check for typeWriter
    try {
        await typeWriter(finalDiv, responseText);
    } catch (err) {
        finalDiv.innerHTML = responseText; // Fallback
    }
}

// Special Command Handler
function checkForSlashCommands(text) {
    if (text.trim() === '/reset' || text.trim() === '/clear') {
        // Clear UI
        chatContainer.innerHTML = '';
        // Also hit server reset
        fetch('/reset', { method: 'POST' });
        // Re-show welcome maybe?
        if (emptyState) emptyState.style.display = 'flex';
        return true;
    }
    return false;
}

function wait(ms) { return new Promise(r => setTimeout(r, ms)); }
function scrollToBottom() { chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: 'smooth' }); }
function escapeHtml(text) { const d = document.createElement('div'); d.textContent = text; return d.innerHTML; }

window.toggleCoT = (id) => {
    const logs = document.getElementById(`${id}-logs`);
    const arrow = document.getElementById(`${id}-arrow`);
    if (logs.classList.contains('hidden')) {
        logs.classList.remove('hidden'); arrow.classList.add('rotate-180');
    } else {
        logs.classList.add('hidden'); arrow.classList.remove('rotate-180');
    }
};

async function typeWriter(element, text) {
    // FORMAT THE TEXT BEFORE TYPING
    const formatted = formatText(text);

    // We need to be careful with HTML tags in typewriter mode.
    // If we type character by character, we'll break tags like <strong>.
    // Solution: Split by HTML tags and text nodes.

    // Regex to match tags or text
    const parts = formatted.split(/(<[^>]+>)/g);

    element.innerHTML = '';

    for (let part of parts) {
        if (part.startsWith('<') && part.endsWith('>')) {
            // It's a tag (like <br> or <strong>), append it immediately
            element.innerHTML += part;
        } else {
            // It's text, type it out character by character
            const chars = part.split('');
            for (let char of chars) {
                element.innerHTML += char;
                if (char === '.') await wait(200); else await wait(15);
                scrollToBottom();
            }
        }
    }
}

window.addEventListener('load', () => {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    if (window.lucide) window.lucide.createIcons();
});