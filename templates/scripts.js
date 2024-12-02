function startServer() {
    fetch('/start', { method: 'POST' }) // 使用fetch发起请求，指定方法为post
        .then(response => response.json()) // 回调函数，当Promise解决后转化为JSON格式
        .then(data => { // 另一个回调函数，返回id为 status 的值
            document.getElementById('status').innerText = data.status;
            startLogFetching();
        });
}

function stopServer() {
    fetch('/stop', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            document.getElementById('status').innerText = data.status;
        });
}

function sendCommand() {
    const command = document.getElementById('commandInput').value;
    fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: command })
    })
        .then(response => response.json())
        .then(data => {
            document.getElementById('status').innerText = data.status;
        });
}

function startLogFetching() {
    setInterval(() => {
        fetch('/logs', { method: 'GET' })
            .then(response => response.json())
            .then(data => {
                document.getElementById('logs').innerText = data.join('\n');
            })
            .catch(error => {
                console.error('Error fetching logs:', error);
            });
    }, 1000);
}

document.getElementById('logoutButton').addEventListener('click', function(){
    window.location.href = '/logout';
});

// 命令框回车输入
document.getElementById('commandInput').addEventListener('keydown', function(event) {
    if (event.key === 'Enter') {
        sendCommand();
    }
});
