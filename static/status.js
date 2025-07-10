// ⚙️ 获取服务器状态信息
async function getServerStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        // ⚙️ 检查心跳状态
        const currentTime = Date.now() / 1000;
        const heartbeatAge = currentTime - data.last_heartbeat;
        const heartbeatTimeout = 60; // 60秒超时
        const isHeartbeatOk = data.worker_alive && heartbeatAge < heartbeatTimeout;
        
        // ⚙️ 更新UI基于心跳状态
        const statusElement = document.getElementById('serverStatus');
        if (statusElement) {
            if (isHeartbeatOk) {
                statusElement.innerHTML = '🟢 翻译服务运行中';
                statusElement.classList.add('running');
                statusElement.classList.remove('stopped');
                console.log("Heartbeat OK - 服务正常运行中", {
                    heartbeatAge: Math.round(heartbeatAge) + "秒前",
                    workerAlive: data.worker_alive
                });
            } else {
                statusElement.innerHTML = '🔴 翻译服务已停止';
                statusElement.classList.add('stopped');
                statusElement.classList.remove('running');
                console.log("Worker appears stopped", {
                    heartbeatAge: Math.round(heartbeatAge) + "秒前",
                    workerAlive: data.worker_alive
                });
            }
        }
        
        // 更新房间信息
        const roomsElement = document.getElementById('roomInfo');
        if (roomsElement && data.rooms) {
            roomsElement.innerHTML = `
                <div>中文原音房间: ${data.rooms.chinese}</div>
                <div>韩文翻译房间: ${data.rooms.korean}</div>
                <div>越南文翻译房间: ${data.rooms.vietnamese}</div>
            `;
        }
        
        return data;
    } catch (error) {
        console.error('获取服务器状态失败:', error);
        // ⚙️ 连接失败时更新UI
        const statusElement = document.getElementById('serverStatus');
        if (statusElement) {
            statusElement.innerHTML = '🔴 无法连接到服务器';
            statusElement.classList.add('stopped');
            statusElement.classList.remove('running');
        }
        return null;
    }
}

// ⚙️ 页面加载后自动获取服务器状态
document.addEventListener('DOMContentLoaded', () => {
    // 初始获取状态
    getServerStatus();
    
    // ⚙️ 每15秒更新一次状态 (更频繁检查心跳)
    setInterval(getServerStatus, 15000);
    
    // 添加健康检查按钮事件
    const healthCheckBtn = document.getElementById('healthCheckBtn');
    if (healthCheckBtn) {
        healthCheckBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/health');
                const data = await response.json();
                
                // 同时检查状态
                const statusData = await getServerStatus();
                
                if (data.status === 'ok' && statusData && statusData.worker_alive) {
                    alert(`服务健康状态: 正常\n心跳: ${Math.round(Date.now()/1000 - statusData.last_heartbeat)}秒前`);
                } else if (data.status === 'ok') {
                    alert(`API服务: 正常\n但Worker心跳异常，可能需要重启服务`);
                } else {
                    alert(`服务健康状态: 异常`);
                }
            } catch (error) {
                alert('健康检查失败: ' + error.message);
            }
        });
    }
}); 
