function showToast(message, iconClass = 'fa-check-circle') {
    let toast = document.getElementById("toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast";
        document.body.appendChild(toast);
    }
    toast.innerHTML = `<i class="fas ${iconClass}"></i> ${message}`;
    toast.className = "show";
    setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 3000);
}

document.addEventListener('DOMContentLoaded', () => {

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) entry.target.classList.add('active');
        });
    });
    document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

    const themeBtn = document.getElementById('theme-toggle');
    function aplicarTema(isDark) {
        if (isDark) document.body.classList.add('dark-mode');
        else document.body.classList.remove('dark-mode');
        
        if(themeBtn) {
            const icon = themeBtn.querySelector('i');
            if(icon) icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        }
    }
    if (localStorage.getItem('theme') === 'dark') aplicarTema(true);
    if (themeBtn) {
        themeBtn.addEventListener('click', () => {
            document.body.classList.toggle('dark-mode');
            const isDark = document.body.classList.contains('dark-mode');
            localStorage.setItem('theme', isDark ? 'dark' : 'light');
            aplicarTema(isDark);
        });
    }

    const telInputs = document.querySelectorAll('input[type="tel"]');
    telInputs.forEach(input => {
        input.addEventListener('input', (e) => {
            let v = e.target.value.replace(/\D/g, '');
            if(v.length > 11) v = v.slice(0, 11);
            const m = v.match(/^(\d{0,2})(\d{0,5})(\d{0,4})$/);
            if(m) e.target.value = !m[2] ? m[1] : `(${m[1]}) ${m[2]}${m[3] ? '-' + m[3] : ''}`;
        });
    });

    const leadForm = document.getElementById('leadForm');
    if(leadForm) {
        leadForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = leadForm.querySelector('button');
            const txt = btn.innerText; 
            btn.innerText='Enviando...'; btn.disabled=true;
            try {
                await fetch('/submit_lead', {method:'POST', body: new FormData(leadForm)});
                showToast('Solicitação enviada!');
                leadForm.reset();
            } catch(e) { showToast('Erro ao enviar', 'fa-times'); }
            finally { btn.innerText=txt; btn.disabled=false; }
        });
    }

    const chatBox = document.getElementById('chat-box');
    const chatMenu = document.getElementById('chat-menu');
    const chatInterface = document.getElementById('chat-interface');
    const btnContinue = document.getElementById('btn-continue');
    const backBtn = document.getElementById('chat-back-btn');
    const chatBody = document.getElementById('chat-body');
    const chatInput = document.getElementById('chat-input');
    const statusText = document.getElementById('chat-status');

    window.toggleChat = function() {
        chatBox.style.display = (chatBox.style.display === 'flex') ? 'none' : 'flex';
        if(chatBox.style.display === 'flex') {
            if(localStorage.getItem('chatSession')) btnContinue.style.display = 'block';
        }
    }
    if(document.getElementById('chat-toggle')) document.getElementById('chat-toggle').addEventListener('click', toggleChat);

    if(backBtn) {
        backBtn.addEventListener('click', () => {
            chatInterface.style.display = 'none';
            chatMenu.style.display = 'flex';
            backBtn.style.display = 'none';
            statusText.innerText = "Atendimento Virtual";
        });
    }

    window.startTicket = async function(categoria) {
        localStorage.removeItem('chatSession');
        localStorage.removeItem('chatTicket');
        localStorage.removeItem('chatStep');
        chatBody.innerHTML = '';
        
        chatMenu.style.display = 'none';
        chatInterface.style.display = 'flex';
        backBtn.style.display = 'block'; 
        statusText.innerText = `Iniciando: ${categoria}...`;

        try {
            const res = await fetch('/init_session', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ category: categoria })
            });
            const data = await res.json();
            
            localStorage.setItem('chatSession', data.session_id);
            localStorage.setItem('chatTicket', data.ticket);
            statusText.innerText = data.ticket;

            appendMessage(`Opção: <b>${categoria}</b>.`, 'received', true);
            appendMessage(`Ticket ${data.ticket} criado.`, 'received');
            setTimeout(() => {
                appendMessage("Informe seu **Nome e Telefone**:", 'received', true);
            }, 800);
            
            localStorage.setItem('chatStep', '1'); 
        } catch(e) { console.error(e); }
    }

    window.continueChat = function() {
        chatMenu.style.display = 'none';
        chatInterface.style.display = 'flex';
        backBtn.style.display = 'block'; 
        
        statusText.innerText = localStorage.getItem('chatTicket') || "Atendimento";
        localStorage.setItem('chatStep', '3');
        loadMessages();
    }

    async function handleSend() {
        const text = chatInput.value.trim();
        if(!text) return;
        
        appendMessage(text, 'sent');
        chatInput.value = '';

        const step = localStorage.getItem('chatStep');
        if (step === '1') {
            const fd = new FormData(); fd.append('message', text);
            await sendMessageBackend(fd);
            
            setTimeout(() => {
                appendMessage("Obrigado! Um atendente irá assumir.", 'received');
                localStorage.setItem('chatStep', '3'); 
            }, 800);
        } else {
            const fd = new FormData(); fd.append('message', text);
            await sendMessageBackend(fd);
        }
    }

    if(document.getElementById('btn-send')) {
        document.getElementById('btn-send').addEventListener('click', handleSend);
        chatInput.addEventListener('keypress', (e)=>{ if(e.key==='Enter') handleSend(); });
    }

    async function sendMessageBackend(fd) {
        const sess = localStorage.getItem('chatSession');
        if(!sess) return;
        fd.append('session_id', sess);
        fd.append('remetente', 'user');
        await fetch('/send_chat', {method:'POST', body:fd});
    }

    function appendMessage(content, type, isHtml=false) {
        const div = document.createElement('div');
        div.className = `message ${type}`;
        if(isHtml) div.innerHTML = content; else div.innerText = content;
        chatBody.appendChild(div);
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    async function loadMessages() {
        const sess = localStorage.getItem('chatSession');
        const step = localStorage.getItem('chatStep');
        
        if(!sess || chatInterface.style.display === 'none' || step === '1') return;

        try {
            const res = await fetch(`/get_messages/${sess}`);
            const msgs = await res.json();
            
            chatBody.innerHTML = ''; 
            msgs.forEach(m => {
                let c = m.conteudo;
                if(m.tipo === 'audio') c = `<audio controls src="/static/uploads/${c}"></audio>`;
                if(m.tipo === 'arquivo') c = `<a href="/static/uploads/${c}" target="_blank">Ver Anexo</a>`;
                
                const type = m.remetente === 'user' ? 'sent' : 'received';
                appendMessage(c, type, true);
            });
        } catch(e) {}
    }
    setInterval(loadMessages, 3000);

    const btnMic = document.getElementById('btn-mic');
    if(btnMic) {
        let mediaRecorder; let audioChunks=[];
        btnMic.addEventListener('mousedown', async()=>{
            try {
                const stream = await navigator.mediaDevices.getUserMedia({audio:true});
                mediaRecorder = new MediaRecorder(stream);
                audioChunks=[];
                mediaRecorder.ondataavailable=e=>audioChunks.push(e.data);
                mediaRecorder.start();
                btnMic.style.color='red';
            } catch(e) { showToast('Erro mic', 'fa-times'); }
        });
        btnMic.addEventListener('mouseup', ()=>{
            if(mediaRecorder && mediaRecorder.state!=='inactive'){
                mediaRecorder.stop(); btnMic.style.color='';
                mediaRecorder.onstop = async()=>{
                    const blob = new Blob(audioChunks,{type:'audio/webm'});
                    const url = URL.createObjectURL(blob);
                    appendMessage(`<audio controls src="${url}"></audio>`, 'sent', true);
                    const fd = new FormData(); fd.append('audio', blob, 'voice.webm');
                    await sendMessageBackend(fd);
                };
            }
        });
    }

    const fileInput = document.getElementById('file-input');
    const btnAttach = document.getElementById('btn-attach');
    if(btnAttach && fileInput) {
        btnAttach.addEventListener('click', ()=>fileInput.click());
        fileInput.addEventListener('change', async()=>{
            if(fileInput.files.length>0) {
                const file = fileInput.files[0];
                appendMessage(`Enviando: ${file.name}`, 'sent');
                const fd = new FormData(); fd.append('arquivo', file);
                await sendMessageBackend(fd);
            }
        });
    }
});