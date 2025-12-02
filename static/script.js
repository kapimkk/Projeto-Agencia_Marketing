document.addEventListener('DOMContentLoaded', () => {
    
    const themeBtn = document.getElementById('theme-toggle');
    const body = document.body;
    const savedTheme = localStorage.getItem('theme');

    if (savedTheme === 'dark') {
        body.classList.add('dark-mode');
        if (themeBtn) themeBtn.querySelector('i').classList.replace('fa-moon', 'fa-sun');
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            body.classList.toggle('dark-mode');
            const icon = themeBtn.querySelector('i');
            if (body.classList.contains('dark-mode')) {
                icon.classList.replace('fa-moon', 'fa-sun');
                localStorage.setItem('theme', 'dark');
            } else {
                icon.classList.replace('fa-sun', 'fa-moon');
                localStorage.setItem('theme', 'light');
            }
        });
    }

    document.addEventListener('contextmenu', e => e.preventDefault()); 
    document.onkeydown = function(e) { if(e.keyCode == 123) return false; } 

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add('active');
            else entry.target.classList.remove('active');
        });
    });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    let sessionId = localStorage.getItem('chatSession');
    if (!sessionId) {
        sessionId = 'cliente_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('chatSession', sessionId);
        localStorage.setItem('chatStep', '0'); 
    }

    const chatBox = document.getElementById('chat-box');
    const chatInput = document.getElementById('chat-input');
    const chatBody = document.getElementById('chat-body');
    const fileInput = document.getElementById('file-input');

    if (document.getElementById('chat-toggle')) {
        document.getElementById('chat-toggle').addEventListener('click', () => {
            chatBox.style.display = chatBox.style.display === 'flex' ? 'none' : 'flex';
            if (chatBox.style.display === 'flex') runBot();
        });
    }

    function appendMessage(content, type, isHtml = false) {
        if (!chatBody) return;
        const div = document.createElement('div');
        div.classList.add('message', type);
        if (isHtml) div.innerHTML = content; else div.innerText = content;
        chatBody.appendChild(div);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function botTyping(callback) {
        if (!chatBody) return;
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.innerText = 'Digitando...';
        typingDiv.style.display = 'block';
        chatBody.appendChild(typingDiv);
        chatBody.scrollTop = chatBody.scrollHeight;

        setTimeout(() => {
            typingDiv.remove();
            callback();
        }, 1000); 
    }

    async function saveToBackend(text, type='texto', file=null, remetente='user') {
        const formData = new FormData();
        formData.append('session_id', sessionId);
        formData.append('remetente', remetente);
        
        if (type === 'texto') formData.append('message', text);
        else if (type === 'arquivo') formData.append('arquivo', file);
        else if (type === 'audio') formData.append('audio', file, 'voice.webm');

        try { await fetch('/send_chat', { method: 'POST', body: formData }); } 
        catch(e) { console.error("Erro ao sincronizar chat:", e); }
    }

    function runBot() {
        if (!chatBody) return;
        let step = parseInt(localStorage.getItem('chatStep') || '0');
        
        if (chatBody.children.length === 0) {
            if (step === 0) {
                botTyping(() => {
                    const msg = "Olá! Bem-vindo. Qual seu nome e telefone?";
                    appendMessage(msg, 'received');
                    saveToBackend(msg, 'texto', null, 'bot');
                });
            } else {
                appendMessage("Histórico restaurado.", 'received');
            }
        }
    }

    async function handleUserMessage(text) {
        appendMessage(text, 'sent');
        chatInput.value = '';
        
        await saveToBackend(text, 'texto', null, 'user');

        let step = parseInt(localStorage.getItem('chatStep') || '0');

        if (step === 0) {
            botTyping(() => {
                const msg = `Obrigado! Selecione uma opção abaixo:`;
                appendMessage(msg, 'received');
                saveToBackend(msg, 'texto', null, 'bot');
                showOptions();
            });
            localStorage.setItem('chatStep', '1');
        } 
        else if (step === 1) {
            botTyping(() => {
                const msg = "Entendido. Um especialista vai analisar e te chamar.";
                appendMessage(msg, 'received');
                saveToBackend(msg, 'texto', null, 'bot');
            });
            localStorage.setItem('chatStep', '2');
        }
    }

    function showOptions() {
        const div = document.createElement('div');
        div.className = 'chat-options';
        div.innerHTML = `
            <button onclick="userClickedOption('Planos')">Planos</button>
            <button onclick="userClickedOption('Suporte')">Suporte</button>
            <button onclick="userClickedOption('Financeiro')">Financeiro</button>
        `;
        chatBody.appendChild(div);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    window.userClickedOption = function(opt) {
        const opts = document.querySelector('.chat-options');
        if(opts) opts.remove();
        
        appendMessage(opt, 'sent');
        saveToBackend(`[Clicou]: ${opt}`, 'texto', null, 'user');
        
        botTyping(() => {
            const msg = "Perfeito! Aguarde um momento.";
            appendMessage(msg, 'received');
            saveToBackend(msg, 'texto', null, 'bot');
        });
        localStorage.setItem('chatStep', '2');
    };


    if (document.getElementById('btn-send')) {
        document.getElementById('btn-send').addEventListener('click', () => {
            const text = chatInput.value.trim();
            if(text) handleUserMessage(text);
        });
        chatInput.addEventListener('keypress', (e) => {
            if(e.key === 'Enter') {
                const text = chatInput.value.trim();
                if(text) handleUserMessage(text);
            }
        });
    }


    if (document.getElementById('btn-attach')) {
        document.getElementById('btn-attach').addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', async () => {
            if (fileInput.files.length > 0) {
                const file = fileInput.files[0];
                appendMessage(`Enviando ${file.name}...`, 'sent');
                await saveToBackend(null, 'arquivo', file, 'user');
                appendMessage("Arquivo enviado com sucesso.", 'sent');
            }
        });
    }
    const reviewForm = document.getElementById('reviewForm');
    if (reviewForm) {
        reviewForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = reviewForm.querySelector('button');
            const txt = btn.innerText;
            btn.innerText = 'Enviando...';

            const selectedStar = document.querySelector('input[name="rating"]:checked');
            const rating = selectedStar ? selectedStar.value : 0;

            const data = {
                nome: document.getElementById('rev_nome').value,
                email: document.getElementById('rev_email').value,
                empresa: document.getElementById('rev_empresa').value,
                avaliacao: document.getElementById('rev_texto').value,
                estrelas: rating
            };

            await fetch('/submit_review', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });

            alert('Obrigado pela sua avaliação!');
            reviewForm.reset();
            btn.innerText = txt;
        });
    }

    const leadForm = document.getElementById('leadForm');
    if(leadForm) {
        leadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = leadForm.querySelector('button');
            const txt = btn.innerText;
            btn.innerText = 'Enviando...';
            const data = {
                nome: document.getElementById('nome').value,
                email: document.getElementById('email').value,
                telefone: document.getElementById('telefone').value,
                projeto: document.getElementById('projeto').value
            };
            await fetch('/submit_lead', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            alert('Recebemos sua proposta!');
            leadForm.reset();
            btn.innerText = txt;
        });
    }
});