document.addEventListener('DOMContentLoaded', () => {
    const messagesList = document.getElementById('messages-list');
    const textForm = document.getElementById('text-form');
    const textInput = document.getElementById('text-input');
    const imageForm = document.getElementById('image-form');
    const imageFileInput = document.getElementById('image-file');
    const selectedFileName = document.getElementById('selected-file-name');

    let lastMessagesJson = '';

    // Format ISO UTC timestamp to local readable time
    function formatTime(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    // Fetch messages from server API (server enforces 3-min / 10-msg limit)
    async function fetchMessages() {
        try {
            const res = await fetch('/api/messages');
            if (res.status === 401) {
                // Inactivity session expiration -> redirect to login
                window.location.href = '/login';
                return;
            }
            if (!res.ok) return;

            const data = await res.json();
            const currentJson = JSON.stringify(data.messages);
            
            // Only re-render if message list changed
            if (currentJson !== lastMessagesJson) {
                lastMessagesJson = currentJson;
                renderMessages(data.messages);
            }
        } catch (err) {
            console.error('Error fetching messages:', err);
        }
    }

    // Render list of message objects
    function renderMessages(messages) {
        messagesList.innerHTML = '';
        if (!messages || messages.length === 0) {
            messagesList.innerHTML = '<div style="text-align:center; color:#999; margin-top:20px; font-size:0.9rem;">No messages</div>';
            return;
        }

        messages.forEach(msg => {
            const item = document.createElement('div');
            const isUser = msg.sender === 'USER';
            item.className = `message-item ${isUser ? 'sent-user' : 'sent-admin'}`;

            const bubble = document.createElement('div');
            bubble.className = 'message-bubble';

            if (msg.type === 'text') {
                bubble.textContent = msg.text;
            } else if (msg.type === 'image' && msg.image_url) {
                const img = document.createElement('img');
                img.src = msg.image_url;
                img.alt = 'Uploaded image';
                img.className = 'message-image';
                bubble.appendChild(img);
            }

            const meta = document.createElement('div');
            meta.className = 'message-meta';
            meta.textContent = `${msg.sender} • ${formatTime(msg.created_at)}`;

            item.appendChild(bubble);
            item.appendChild(meta);
            messagesList.appendChild(item);
        });

        // Scroll to bottom
        messagesList.scrollTop = messagesList.scrollHeight;
    }

    // Send text message
    if (textForm) {
        textForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const text = textInput.value.trim();
            if (!text) return;

            try {
                const res = await fetch('/api/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text })
                });

                if (res.status === 401) {
                    window.location.href = '/login';
                    return;
                }

                if (res.ok) {
                    textInput.value = '';
                    fetchMessages();
                } else {
                    const errData = await res.json();
                    alert(errData.error || 'Failed to send message');
                }
            } catch (err) {
                console.error('Error sending message:', err);
            }
        });
    }

    // Handle image selection label display
    if (imageFileInput) {
        imageFileInput.addEventListener('change', () => {
            if (imageFileInput.files && imageFileInput.files[0]) {
                selectedFileName.textContent = imageFileInput.files[0].name;
            } else {
                selectedFileName.textContent = 'No file selected';
            }
        });
    }

    // Upload image message
    if (imageForm) {
        imageForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (!imageFileInput.files || !imageFileInput.files[0]) {
                alert('Please select an image first');
                return;
            }

            const formData = new FormData();
            formData.append('file', imageFileInput.files[0]);

            try {
                const res = await fetch('/api/upload-image', {
                    method: 'POST',
                    body: formData
                });

                if (res.status === 401) {
                    window.location.href = '/login';
                    return;
                }

                if (res.ok) {
                    imageFileInput.value = '';
                    selectedFileName.textContent = 'No file selected';
                    fetchMessages();
                } else {
                    const errData = await res.json();
                    alert(errData.error || 'Failed to upload image');
                }
            } catch (err) {
                console.error('Error uploading image:', err);
            }
        });
    }

    // Initial fetch and 1.5-second polling interval
    fetchMessages();
    setInterval(fetchMessages, 1500);
});
