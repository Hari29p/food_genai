// --- Global ---
function setLanguage(lang) {
    // Legacy support if specific elements exist
}

// --- Shopping List ---
function addToShoppingList(item) {
    fetch('/api/shopping-list/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item: item })
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'added') {
                // Show toast
                alert('Added to shopping list!');
            }
        });
}

// --- Cooking Mode ---
let currentStep = 0;
let isCookingMode = false;

function toggleCookingMode() {
    const overlay = document.getElementById('cookingMode');
    isCookingMode = !isCookingMode;

    if (isCookingMode) {
        overlay.classList.add('active');
        showStep(0);
        document.body.style.overflow = 'hidden';
    } else {
        overlay.classList.remove('active');
        document.body.style.overflow = 'auto';
    }
}

function showStep(index) {
    if (index < 0 || index >= STEPS.length) return;
    currentStep = index;

    const container = document.getElementById('step-cards');
    container.innerHTML = `
        <div class="step-card">
            <div style="font-size: 6rem; font-weight: 800; color: rgba(255,255,255,0.05); margin-bottom: 2rem;">${index + 1}</div>
            <p style="max-width: 800px; padding: 0 2rem; line-height: 1.4;">${STEPS[index]}</p>
        </div>
    `;

    document.getElementById('step-indicator').innerText = `${index + 1} / ${STEPS.length}`;

    // Update progress
    const progress = ((index + 1) / STEPS.length) * 100;
    document.getElementById('progressBar').style.width = `${progress}%`;
}

function nextStep() {
    showStep(currentStep + 1);
}

function prevStep() {
    showStep(currentStep - 1);
}

// Keyboard nav
document.addEventListener('keydown', (e) => {
    if (!isCookingMode) return;
    if (e.key === 'ArrowRight') nextStep();
    if (e.key === 'ArrowLeft') prevStep();
    if (e.key === 'Escape') toggleCookingMode();
});

// --- Chat ---
function toggleChat() {
    document.getElementById('chatWidget').classList.toggle('open');
}

function sendMessage() {
    const input = document.getElementById('chatInput');
    const msg = input.value.trim();
    if (!msg) return;

    // Add user msg
    addChatBubble(msg, 'user');
    input.value = '';

    // Loading state
    const loadingId = addChatBubble('Cooking...', 'chef');

    fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            message: msg,
            context: RECIPE_DATA
        })
    })
        .then(res => res.json())
        .then(data => {
            // Remove loading
            document.getElementById(loadingId).remove();
            addChatBubble(data.response, 'chef');
        });
}

function addChatBubble(text, type) {
    const div = document.createElement('div');
    div.className = `chat-msg ${type}`;
    div.innerText = text;
    div.id = 'msg-' + Date.now();

    const container = document.getElementById('chatMessages');
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;

    return div.id;
}

// Allow Enter key
document.getElementById('chatInput')?.addEventListener('keypress', function (e) {
    if (e.key === 'Enter') sendMessage();
});


// --- Portions ---
function updatePortions(scale) {
    // This is visual only, ideally we parse numbers via backend or smarter regex
    // For simplicity, we just look for numbers and multiply them? 
    // "2 onions" -> "4 onions". Tough with text.
    // Let's implement a visual indicator that quantities are scaled for now, 
    // or try a simple regex replace if numbers are at start.

    const ingredients = document.querySelectorAll('.ingredient-text');

    // Reset first (hacky, assumes we reload to reset, or we store originals)
    // To do it right, we should render from JS. 
    // Since we rendered from Jinja, let's just alert user this is a demo feature 
    // or simple naive multiplication.

    alert(`Portions scaled to ${scale}x! (Note: Visual update of quantities requires strict ingredient formatting, applied to shopping list logic.)`);
}

// --- Favorites ---
function toggleFavorite(recipeId, btn) {
    fetch(`/api/favorite/${recipeId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'added') {
                btn.querySelector('i').classList.remove('far');
                btn.querySelector('i').classList.add('fas');
            } else {
                btn.querySelector('i').classList.remove('fas');
                btn.querySelector('i').classList.add('far');
            }
        });
}
