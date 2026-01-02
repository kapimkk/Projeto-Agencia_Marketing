// --- Configuração das Notificações (Toast) ---
const Toast = Swal.mixin({
    toast: true,
    position: 'bottom-end',
    showConfirmButton: false,
    timer: 3000,
    timerProgressBar: true,
    background: 'rgba(255, 255, 255, 0.9)',
    color: '#1d1d1d',
    didOpen: (toast) => {
        toast.addEventListener('mouseenter', Swal.stopTimer)
        toast.addEventListener('mouseleave', Swal.resumeTimer)
    }
});

function showToast(message, icon = 'success') {
    Toast.fire({ icon: icon, title: message });
}

function showAlert(title, text) {
    Swal.fire({
        title: title,
        text: text,
        icon: 'warning',
        confirmButtonColor: '#1d1d1d',
        background: 'rgba(255, 255, 255, 0.95)',
        backdrop: `rgba(0,0,0,0.4)`
    });
}

// Alterna a exibição da tabela de comparação de planos
function toggleComparison() {
    const section = document.getElementById('comparison-section');
    if (section.style.display === 'none' || section.style.display === '') {
        section.style.display = 'block';
        section.classList.add('active');
        window.scrollTo({
            top: section.offsetTop - 100,
            behavior: 'smooth'
        });
    } else {
        section.style.display = 'none';
    }
}

// --- Inicialização do Gráfico de ROI (Canvas) ---
function initROIChart() {
    const ctx = document.getElementById('roiChart');
    if(!ctx) return;
    
    if (window.roiChartInstance) {
        window.roiChartInstance.destroy();
    }
    
    window.roiChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Mês 1', 'Mês 2', 'Mês 3', 'Mês 4', 'Mês 5', 'Mês 6'],
            datasets: [{
                label: 'Crescimento de Faturamento (R$)',
                data: [10000, 18000, 29000, 45000, 68000, 95000],
                borderColor: '#1D1D1D',
                backgroundColor: 'rgba(29, 29, 29, 0.05)',
                tension: 0.4,
                fill: true,
                pointRadius: 5,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { font: { family: 'Poppins' } } }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: function(value) { return 'R$ ' + value/1000 + 'k'; } }
                }
            },
            animation: {
                duration: 2000,
                easing: 'easeOutQuart'
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // Observador para animar elementos quando aparecem na tela
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => { if(e.isIntersecting) e.target.classList.add('active'); });
    });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
    
    // Observador para carregar o gráfico apenas quando visível
    const chartObserver = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if(e.isIntersecting) {
                initROIChart();
                chartObserver.unobserve(e.target);
            }
        });
    });
    const roiSection = document.getElementById('results-graph');
    if(roiSection) chartObserver.observe(roiSection);

    // Formatação de Telefone
    const telInputs = document.querySelectorAll('input[type="tel"]');
    telInputs.forEach(input => {
        input.addEventListener('input', (e) => {
            let v = e.target.value.replace(/\D/g, '');
            if(v.length > 11) v = v.slice(0, 11);
            const m = v.match(/^(\d{0,2})(\d{0,5})(\d{0,4})$/);
            if(m) e.target.value = !m[2] ? m[1] : `(${m[1]}) ${m[2]}${m[3] ? '-' + m[3] : ''}`;
        });
    });

    // --- Envio do Formulário de Lead (Orçamento) ---
    const leadForm = document.getElementById('leadForm');
    if(leadForm) {
        leadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = leadForm.querySelector('button');
            const txt = btn.innerText; btn.innerText='Enviando...'; btn.disabled=true;
            try {
                const res = await fetch('/submit_lead', {method:'POST', body: new FormData(leadForm)});
                if(res.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Recebemos seu contato!',
                        html: `
                            <p>Nossa equipe entrará em contato em breve.</p>
                            <p style="margin-top:10px;">Tem urgência ou ficou com dúvida?</p>
                            <a href="https://wa.me/5511999999999?text=Olá,%20enviei%20um%20lead%20pelo%20site" target="_blank" 
                               style="display:inline-block; margin-top:15px; background:#25d366; color:white; padding:10px 20px; border-radius:20px; text-decoration:none; font-weight:bold;">
                               <i class="fab fa-whatsapp"></i> Chamar no WhatsApp
                            </a>
                        `,
                        showConfirmButton: false, // Remove o botão "OK" padrão para destacar o WhatsApp
                        showCloseButton: true,
                        background: 'rgba(255,255,255,0.95)'
                    });
                    leadForm.reset();
                } else throw new Error();
            } catch(e) { showToast('Erro ao enviar', 'error'); }
            finally { btn.innerText=txt; btn.disabled=false; }
        });
    }

    // --- Envio de Avaliação ---
    const reviewForm = document.getElementById('reviewForm');
    if(reviewForm) {
        reviewForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const star = document.querySelector('input[name="rating"]:checked');
            if(!star) return Swal.fire('Atenção', 'Selecione uma estrela!', 'warning');
            
            const btn = reviewForm.querySelector('button');
            btn.disabled = true;
            const dados = {
                nome: document.getElementById('rev_nome').value,
                empresa: document.getElementById('rev_empresa').value,
                email: document.getElementById('rev_email').value,
                avaliacao: document.getElementById('rev_texto').value,
                estrelas: star.value
            };
            try {
                const res = await fetch('/submit_review', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify(dados)
                });
                if(res.ok) {
                    Swal.fire('Obrigado!', 'Avaliação enviada.', 'success');
                    reviewForm.reset();
                }
            } catch(e) { showToast('Erro', 'error'); }
            finally { btn.disabled = false; }
        });
    }

    // --- LÓGICA DO CHATBOT ---
    const chatBox = document.getElementById('chat-box');
    const chatMenu = document.getElementById('chat-menu');
    const chatInterface = document.getElementById('chat-interface');
    const chatHistoryView = document.getElementById('chat-history-view');
    const backBtn = document.getElementById('chat-back-btn');
    const chatBody = document.getElementById('chat-body');
    const chatInput = document.getElementById('chat-input');
    const statusText = document.getElementById('chat-status');
    const historyList = document.getElementById('history-list');

    let botState = 'idle';
    let tempCategory = '', tempName = '';
    let currentMessageCount = 0;
    let isUploadingAudio = false;

    // Abrir/Fechar Chat
    window.toggleChat = function() {
        chatBox.style.display = (chatBox.style.display === 'flex') ? 'none' : 'flex';
        if(chatBox.style.display === 'flex') resetToMenu();
    }
    if(document.getElementById('chat-toggle')) document.getElementById('chat-toggle').addEventListener('click', toggleChat);

    // Reseta para o menu inicial do chat
    window.resetToMenu = function() {
        chatMenu.style.display = 'flex'; chatInterface.style.display = 'none';
        if(chatHistoryView) chatHistoryView.style.display = 'none';
        backBtn.style.display = 'none'; statusText.innerText = "Suporte Online";
        botState = 'idle'; localStorage.removeItem('activeSession');
        currentMessageCount = 0;
        isUploadingAudio = false;
    }
    if(backBtn) backBtn.addEventListener('click', () => window.resetToMenu());

    // Inicia fluxo de criação de ticket
    window.checkAndStart = async function(categoria) {
        // Verifica se já existe ticket
        const history = JSON.parse(localStorage.getItem('ticketHistory') || '[]');
        if (history.length > 0) {
            try {
                const res = await fetch('/my_tickets', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ uuids: history }) });
                const tickets = await res.json();
                const openTicket = tickets.find(t => t.category === categoria && t.status === 'Aberto');
                if (openTicket) {
                    showAlert('Ticket Aberto', `Você já possui um atendimento em ${categoria}.`);
                    return;
                }
            } catch(e) {}
        }
        window.startBotFlow(categoria);
    }

    // Fluxo do Robô (Perguntar nome e telefone)
    window.startBotFlow = function(categoria) {
        chatMenu.style.display = 'none'; chatInterface.style.display = 'flex';
        backBtn.style.display = 'block'; chatBody.innerHTML = ''; 
        localStorage.removeItem('activeSession'); chatInput.disabled = false; chatInput.placeholder = "Digite...";
        tempCategory = categoria; botState = 'waiting_name';
        statusText.innerText = "Atendimento Virtual";
        currentMessageCount = 0;
        appendMessage("Olá! Sou o assistente virtual.", 'received');
        setTimeout(() => {
            appendMessage(`Opção: <b>${categoria}</b>. Qual seu **Nome**?`, 'received', true);
        }, 800);
    }

    // Enviar Mensagem
    async function handleSend() {
        const text = chatInput.value.trim();
        if(!text) return;
        
        if(isUploadingAudio) return;

        if (botState === 'chatting') {
            const sess = localStorage.getItem('activeSession');
            if(sess) {
                appendMessage(text, 'sent');
                chatInput.value = ''; 
                const fd = new FormData(); fd.append('message', text);
                
                try {
                    await sendMessageBackend(fd, sess);
                    currentMessageCount++; 
                } catch(e) { console.error("Erro ao enviar", e); }
            }
        } else {
            // Lógica do bot simples
            appendMessage(text, 'sent'); chatInput.value = '';
            if (botState === 'waiting_name') {
                tempName = text; botState = 'waiting_phone';
                setTimeout(() => appendMessage(`Prazer ${tempName}. Qual seu **Telefone**?`, 'received', true), 600);
            } else if (botState === 'waiting_phone') {
                const phone = text; botState = 'creating_ticket';
                appendMessage("Criando ticket...", 'received');
                try {
                    const res = await fetch('/init_session', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ category: tempCategory, name: tempName, phone: phone }) });
                    const data = await res.json();
                    saveTicketToLocal(data.session_id); localStorage.setItem('activeSession', data.session_id);
                    statusText.innerText = data.ticket;
                    setTimeout(() => { appendMessage(`Ticket ${data.ticket} criado!`, 'received'); botState = 'chatting'; }, 1000);
                } catch(e) { botState = 'idle'; }
            }
        }
    }

    if(document.getElementById('btn-send')) {
        document.getElementById('btn-send').addEventListener('click', handleSend);
        chatInput.addEventListener('keypress', (e)=>{ if(e.key==='Enter') handleSend(); });
    }

    // --- Upload de Arquivos ---
    const fileInput = document.getElementById('file-input');
    const btnAttach = document.getElementById('btn-attach');
    if(btnAttach && fileInput) {
        btnAttach.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', async () => {
            const sess = localStorage.getItem('activeSession');
            if(fileInput.files.length > 0 && sess) {
                const fd = new FormData(); fd.append('arquivo', fileInput.files[0]);
                appendMessage(`Arquivo: ${fileInput.files[0].name}`, 'sent');
                
                isUploadingAudio = true;
                chatInput.disabled = true;
                chatInput.placeholder = "Enviando arquivo...";
                
                try {
                    await sendMessageBackend(fd, sess);
                    currentMessageCount++;
                } finally {
                    isUploadingAudio = false;
                    chatInput.disabled = false;
                    chatInput.placeholder = "Digite...";
                    chatInput.focus();
                }
            }
        });
    }

    // --- Gravação de Áudio ---
    const btnMic = document.getElementById('btn-mic');
    let mediaRecorder = null;
    let audioChunks = [];
    let isRecording = false;
    let lastMicClick = 0; 
    let recordingStartTime = 0; 

    if(btnMic) {
        btnMic.addEventListener('click', async () => {
            if(!localStorage.getItem('activeSession')) return Swal.fire('Ops', 'Inicie um chat primeiro.', 'warning');
            
            const now = Date.now();
            if (now - lastMicClick < 1000) return; // Evita duplo clique rápido
            lastMicClick = now;

            if(isUploadingAudio) return;

            const icon = btnMic.querySelector('i');

            if (!isRecording) {
                // Iniciar Gravação
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];
                    
                    mediaRecorder.ondataavailable = e => {
                        if (e.data.size > 0) audioChunks.push(e.data);
                    };
                    
                    mediaRecorder.onstop = async () => {
                        const duration = Date.now() - recordingStartTime;
                        if (duration < 1500) {
                            showToast('Áudio muito curto!', 'warning');
                            isUploadingAudio = false;
                            isRecording = false;
                            btnMic.classList.remove('recording-now');
                            if(icon) icon.className = 'fas fa-microphone';
                            return; 
                        }

                        isUploadingAudio = true;
                        
                        const tempId = 'temp-audio-' + Date.now();
                        const uploadingDiv = document.createElement('div');
                        uploadingDiv.id = tempId;
                        uploadingDiv.className = 'message sent';
                        uploadingDiv.style.fontStyle = 'italic';
                        uploadingDiv.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Enviando áudio...';
                        chatBody.appendChild(uploadingDiv);
                        chatBody.scrollTop = chatBody.scrollHeight;
                        
                        chatInput.disabled = true;

                        try {
                            const blob = new Blob(audioChunks, { type: 'audio/webm' });
                            
                            if(blob.size > 0) {
                                const fd = new FormData(); 
                                fd.append('audio', blob, 'gravacao.webm'); 
                                await sendMessageBackend(fd, localStorage.getItem('activeSession'));
                                
                                const el = document.getElementById(tempId);
                                if(el) el.remove();
                                currentMessageCount = 0; 
                                await loadMessages();
                            }
                        } catch(err) {
                            console.error("Erro no upload do áudio:", err);
                            showToast("Erro ao enviar áudio", "error");
                        } finally {
                            isUploadingAudio = false;
                            const el = document.getElementById(tempId);
                            if(el) el.remove();
                            
                            chatInput.disabled = false;
                            chatInput.focus();
                            mediaRecorder = null;
                        }
                    };

                    mediaRecorder.start();
                    isRecording = true;
                    recordingStartTime = Date.now(); 
                    btnMic.classList.add('recording-now');
                    if(icon) icon.className = 'fas fa-stop';
                    
                } catch(e) { 
                    console.error(e);
                    Swal.fire('Erro', 'Microfone não permitido.', 'error'); 
                    isRecording = false;
                }
            } else {
                // Parar Gravação
                if(mediaRecorder && mediaRecorder.state !== 'inactive') {
                    mediaRecorder.stop();
                    mediaRecorder.stream.getTracks().forEach(track => track.stop()); 
                }
                
                isRecording = false;
                btnMic.classList.remove('recording-now');
                if(icon) icon.className = 'fas fa-microphone';
            }
        });
    }

    // Salva ID do ticket no navegador
    function saveTicketToLocal(uuid) {
        let history = JSON.parse(localStorage.getItem('ticketHistory') || '[]');
        if(!history.includes(uuid)) { history.push(uuid); localStorage.setItem('ticketHistory', JSON.stringify(history)); }
    }

    // Função auxiliar para enviar ao backend
    async function sendMessageBackend(fd, sess) {
        fd.append('session_id', sess); fd.append('remetente', 'user');
        const res = await fetch('/send_chat', {method:'POST', body:fd});
        const data = await res.json();
        if(data.status === 'closed') { 
            appendMessage(data.msg, 'received'); 
            chatInput.disabled = true; 
            chatInput.placeholder = "Atendimento encerrado.";
        }
    }

    function appendMessage(c, t, h=false) {
        const d = document.createElement('div'); d.className = `message ${t}`;
        if(h) d.innerHTML = c; else d.innerText = c;
        chatBody.appendChild(d); chatBody.scrollTop = chatBody.scrollHeight;
    }

    // Mostra histórico de tickets
    window.showOldTickets = async function() {
        chatMenu.style.display = 'none'; chatHistoryView.style.display = 'flex'; backBtn.style.display = 'block';
        const history = JSON.parse(localStorage.getItem('ticketHistory') || '[]');
        try {
            const res = await fetch('/my_tickets', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ uuids: history }) });
            const data = await res.json();
            historyList.innerHTML = '';
            data.forEach(t => {
                const d = document.createElement('div');
                d.style.cssText = "padding:15px; border-bottom:1px solid #ddd; cursor:pointer;";
                d.innerHTML = `<b>${t.ticket}</b> <span class="badge" style="background:${t.status=='Aberto'?'green':'grey'}">${t.status}</span><br><small>${t.category}</small>`;
                d.onclick = () => { 
                    chatHistoryView.style.display='none'; 
                    chatInterface.style.display='flex'; 
                    localStorage.setItem('activeSession', t.uuid); 
                    statusText.innerText=t.ticket; 
                    botState='chatting'; 
                    currentMessageCount = 0; 
                    loadMessages(); 
                };
                historyList.appendChild(d);
            });
        } catch(e){}
    }

    // Loop para buscar novas mensagens a cada 3 segundos
    async function loadMessages() {
        if(isUploadingAudio || isRecording) return;

        const sess = localStorage.getItem('activeSession');
        if(!sess || chatInterface.style.display === 'none') return;
        
        try {
            const res = await fetch(`/get_messages/${sess}`); 
            const data = await res.json();
            
            if (data.messages.length !== currentMessageCount) {
                chatBody.innerHTML = '';
                data.messages.forEach(m => {
                    let c = m.conteudo;
                    if(m.tipo === 'audio') c = `<audio controls src="/static/uploads/${c}"></audio>`;
                    if(m.tipo === 'arquivo') c = `<a href="/static/uploads/${c}" target="_blank">Ver Arquivo</a>`;
                    appendMessage(c, m.remetente === 'user' ? 'sent' : 'received', true);
                });
                
                currentMessageCount = data.messages.length;
                
                if(data.status === 'Encerrado') {
                    chatInput.disabled = true;
                    chatInput.placeholder = "Atendimento encerrado.";
                } else if(chatInput.disabled && !isUploadingAudio) {
                    chatInput.disabled = false;
                    chatInput.placeholder = "Digite...";
                }
            }
        } catch(e){}
    }
    setInterval(loadMessages, 3000);
});